"""Движок соединения: один websocket, один читатель, один диспетчер, один keepalive.

Низкоуровневая часть SDK. Обычному боту она не нужна: :class:`sukarisebot.Bot`
сам создаёт движок и управляет им.

**Как работает движок.**

* *Читатель* принимает кадры из сокета и никогда не ждёт код бота. Ответ на
  запрос он находит по ``rid`` и передаёт тому, кто ждёт. События ставит в очередь.
* *Диспетчер* берёт события из очереди по одному и вызывает обработчики бота в
  порядке прихода. Пока один обработчик не завершился, следующий не начинается.
* Если обработчики не успевают и очередь (1024 события) заполнилась, самое
  старое событие отбрасывается и считается в ``dropped_events``: сервер
  отключает бота, который отстал слишком сильно, а оставаться на связи важнее
  устаревшего события.
* *Лимитер* держит запрос, превышающий бюджет, до его очереди.
* *Keepalive* раз в 20 секунд отправляет сигнал, чтобы сервер не счёл бота
  ушедшим.
* При потере сокета движок подключается снова с растущей задержкой (от 0,5 до 30
  секунд, со случайным разбросом). Кадр ``Error`` с ``do_not_reconnect`` и
  отказ HTTP 400/401/403/404 прекращают работу навсегда; временный отказ
  сервера (``Error`` без этого признака) — нет, движок повторяет попытку.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from itertools import count
from typing import Protocol

import aiohttp

from .errors import ConnectionRefused, NotConnected, ProtocolError, RequestTimeout, ResponseError
from .limits import Limiter
from .models import Event, SessionMetadata
from .protocol import (
    Frame,
    decode,
    encode,
    error_text,
    frame_type,
    parse_event,
    parse_session,
    wants_no_reconnect,
)

DEFAULT_URL = "wss://production-portal-refb.sukarise.ru/web/botapi"
"""Адрес шлюза ботов по умолчанию. Переопределяется аргументом ``url`` или переменной ``SUKARISEBOT_URL``."""

_MAX_FRAME_BYTES = 256 * 1024
_KEEPALIVE_FRAME = encode("KeepaliveRequest", None, {})
# 404 is not final: a route can be missing for a moment while a release is switched.
_FATAL_STATUSES = frozenset((400, 401, 403))
# A server that sends nothing for this many keepalive intervals is gone, even when the TCP
# connection looks open (a host that vanished without a reset). The server answers every
# keepalive, so a live connection is never silent this long.
_SILENT_INTERVALS = 3
_STABLE_AFTER_SECONDS = 30.0
_BACKOFF_CAP_EXPONENT = 16

log = logging.getLogger("sukarisebot")

type SessionHandler = Callable[[SessionMetadata], Awaitable[None]]
"""Асинхронная функция, которая получает сессию при каждом (пере)подключении."""
type EventHandler = Callable[[Event], Awaitable[None]]
"""Асинхронная функция, которая получает события по одному, в порядке прихода."""
type ArrivalHook = Callable[[Event], None]
"""Обычная функция, которую читатель вызывает в момент прихода события, до очереди."""
type _QueueItem = SessionMetadata | Event


class Requester(Protocol):
    """Всё, что умеет отправить один запрос и вернуть ответный кадр.

    В работе это :class:`Engine`; в тестах — :class:`sukarisebot.RecordingRequester`.
    :class:`BotAPI` зависит только от этого интерфейса, поэтому его можно
    подставить любой свой реализацией.
    """

    async def request(self, type_name: str, category: str, body: Mapping[str, object]) -> Frame:
        """Отправить запрос и дождаться ответа.

        :param type_name: тип запроса, например ``"ChatRequest"``.
        :param category: категория лимита частоты, например ``"chat"``.
        :param body: поля запроса, кроме ``_type`` и ``rid``.
        :returns: ответный кадр.
        :raises ResponseError: сервер отказал.
        """
        ...


def _with_events(url: str, subscriptions: list[str]) -> str:
    if not subscriptions:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}events={','.join(subscriptions)}"


class Engine:
    """Держит одного бота подключённым к одной комнате и проводит его запросы.

    Один движок — один запуск ``run``. Для обычного бота его создаёт
    ``Bot.run``; напрямую движок нужен в тестах и для нестандартных
    подключений.

    :ivar dropped_events: сколько событий отброшено из-за переполненной очереди.
    :ivar connections: сколько раз движок подключался (повторные подключения
        тоже считаются).
    """

    def __init__(
        self,
        *,
        url: str,
        token: str,
        room_id: str,
        subscriptions: Iterable[str],
        on_session: SessionHandler,
        on_event: EventHandler,
        on_arrival: ArrivalHook | None = None,
        reconnect: bool = True,
        request_timeout: float = 10.0,
        keepalive_interval: float = 20.0,
        max_backoff: float = 30.0,
        backoff_base: float = 0.5,
        queue_size: int = 1024,
    ) -> None:
        """Подготовить движок. Подключение начнётся при вызове :meth:`run`.

        :param url: адрес шлюза (``wss://…/web/botapi``).
        :param token: токен бота (``srbot_…``); уходит в заголовке ``api-token``.
        :param room_id: идентификатор комнаты; уходит в заголовке ``room-id``.
        :param subscriptions: названия событий, которые нужно доставлять
            (``chat``, ``user_joined`` и т. д.); уходят в параметре ``events``.
        :param on_session: вызывается при каждом (пере)подключении с данными сессии.
        :param on_event: вызывается диспетчером для каждого события по порядку.
        :param on_arrival: необязательный обычный вызов в момент прихода события, до очереди.
        :param reconnect: подключаться заново после потери связи.
        :param request_timeout: сколько секунд ждать ответ на запрос.
        :param keepalive_interval: как часто отправлять keepalive, в секундах.
        :param max_backoff: наибольшая пауза перед повторным подключением, в секундах.
        :param backoff_base: первая пауза перед повторным подключением, в секундах.
        :param queue_size: размер очереди событий.
        """
        self._url = _with_events(url, sorted(set(subscriptions)))
        self._headers = {"api-token": token, "room-id": room_id}
        self._on_session = on_session
        self._on_event = on_event
        self._on_arrival = on_arrival
        self._reconnect = reconnect
        self._request_timeout = request_timeout
        self._keepalive_interval = keepalive_interval
        self._max_backoff = max_backoff
        self._backoff_base = backoff_base
        self._stop_event = asyncio.Event()
        self._queue: asyncio.Queue[_QueueItem] = asyncio.Queue(maxsize=queue_size)
        self._pending: dict[str, asyncio.Future[Frame]] = {}
        self._rids = count(1)
        self._limiter = Limiter({})
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._last_inbound = time.monotonic()
        self._session: SessionMetadata | None = None
        self.dropped_events = 0
        """Сколько событий отброшено из-за переполненной очереди."""
        self.connections = 0
        """Сколько раз движок подключался, считая повторные подключения."""

    @property
    def session(self) -> SessionMetadata | None:
        """Сессия живого соединения или ``None``, пока соединения нет."""
        return self._session

    async def run(self) -> None:
        """Обслуживать соединение, пока его не остановят или не откажут насовсем.

        Один движок — один вызов ``run``. Метод возвращается, когда вызван
        :meth:`stop` или (при ``reconnect=False``) соединение закончилось.

        :raises ConnectionRefused: сервер отказал навсегда (отозван токен, комната
            недоступна, бот подключился из другого места) либо отказал временно
            при ``reconnect=False``.
        """
        dispatcher = asyncio.create_task(self._dispatch(), name="sukarisebot-dispatch")
        http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=10.0))
        attempt = 0
        try:
            while True:
                started = time.monotonic()
                try:
                    await self._serve(http)
                except aiohttp.WSServerHandshakeError as exc:
                    if exc.status in _FATAL_STATUSES:
                        raise ConnectionRefused(f"сервер отказал в подключении (HTTP {exc.status})") from exc
                    log.warning("рукопожатие отклонено с HTTP %s; повтор", exc.status)
                except ConnectionRefused as exc:
                    # Слово сервера: насовсем завершает работу только отказ, помеченный окончательным.
                    if exc.do_not_reconnect or not self._reconnect:
                        raise
                    log.warning("сервер отказал в подключении: %s; повтор", exc.message)
                except (aiohttp.ClientError, OSError, TimeoutError, ProtocolError) as exc:
                    log.warning("соединение потеряно: %s", exc)
                if self._stop_event.is_set() or not self._reconnect:
                    return
                if time.monotonic() - started > _STABLE_AFTER_SECONDS:
                    attempt = 0
                delay = min(self._max_backoff, self._backoff_base * 2**attempt) * random.uniform(0.5, 1.0)
                attempt = min(attempt + 1, _BACKOFF_CAP_EXPONENT)
                log.info("повторное подключение через %.1f с", delay)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                if self._stop_event.is_set():
                    return
        finally:
            self._stop_event.set()
            dispatcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await dispatcher
            self._fail_pending("соединение закрыто")
            await http.close()

    async def stop(self) -> None:
        """Закрыть соединение и завершить :meth:`run` без повторного подключения."""
        self._stop_event.set()
        ws = self._ws
        if ws is not None and not ws.closed:
            await ws.close()

    async def request(self, type_name: str, category: str, body: Mapping[str, object]) -> Frame:
        """Отправить один запрос и дождаться ответа с учётом лимитов частоты.

        :param type_name: тип запроса, например ``"ChatRequest"``.
        :param category: категория лимита; запрос ждёт, пока в ней есть место.
        :param body: поля запроса, кроме ``_type`` и ``rid``.
        :returns: ответный кадр сервера.
        :raises NotConnected: соединения нет или оно оборвалось при отправке.
        :raises RequestTimeout: ответ не пришёл за ``request_timeout`` секунд.
        :raises ResponseError: сервер отказал в запросе.
        """
        if self._open_socket() is None:
            raise NotConnected("бот не подключён к комнате")
        await self._limiter.acquire(category)
        ws = self._open_socket()  # за время ожидания очереди соединение могло оборваться
        if ws is None:
            raise NotConnected("бот не подключён к комнате")
        rid = str(next(self._rids))
        future: asyncio.Future[Frame] = asyncio.get_running_loop().create_future()
        self._pending[rid] = future
        try:
            await ws.send_str(encode(type_name, rid, body))
            return await asyncio.wait_for(future, timeout=self._request_timeout)
        except TimeoutError as exc:
            raise RequestTimeout(f"{type_name}: нет ответа за {self._request_timeout:g} с") from exc
        except (aiohttp.ClientError, ConnectionError) as exc:
            raise NotConnected("соединение оборвалось при отправке") from exc
        finally:
            self._pending.pop(rid, None)

    # ---- соединение -----------------------------------------------------------

    def _open_socket(self) -> aiohttp.ClientWebSocketResponse | None:
        ws = self._ws
        return None if ws is None or ws.closed else ws

    async def _serve(self, http: aiohttp.ClientSession) -> None:
        async with http.ws_connect(
            self._url,
            headers=self._headers,
            heartbeat=None,
            max_msg_size=_MAX_FRAME_BYTES,
            # Типы aiohttp не описывают поля ClientWSTimeout (attrs): pyright их не видит.
            timeout=aiohttp.ClientWSTimeout(ws_receive=None, ws_close=5.0),  # pyright: ignore[reportCallIssue]
        ) as ws:
            self._ws = ws
            self.connections += 1
            self._last_inbound = time.monotonic()
            keepalive = asyncio.create_task(self._keepalive(ws))
            try:
                await self._handshake(ws)
                async for message in ws:
                    self._last_inbound = time.monotonic()
                    if message.type is aiohttp.WSMsgType.TEXT:
                        self._on_frame(str(message.data))
                    elif message.type is aiohttp.WSMsgType.ERROR:
                        raise aiohttp.ClientConnectionError(f"сбой websocket: {ws.exception()}")
            finally:
                keepalive.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await keepalive
                self._ws = None
                self._session = None
                self._fail_pending("соединение потеряно")

    async def _handshake(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        message = await asyncio.wait_for(ws.receive(), timeout=self._request_timeout)
        if message.type is not aiohttp.WSMsgType.TEXT:
            raise ProtocolError("сервер не начал с кадра сессии")
        frame = decode(str(message.data))
        if frame_type(frame) == "Error":
            raise ConnectionRefused(error_text(frame), wants_no_reconnect(frame))
        if frame_type(frame) != "SessionMetadata":
            raise ProtocolError(f"ожидался SessionMetadata, пришёл {frame_type(frame)}")
        session = parse_session(frame)
        self._session = session
        self._limiter = Limiter(session.rate_limits)
        self._enqueue(session)

    async def _keepalive(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        while True:
            await asyncio.sleep(self._keepalive_interval)
            try:
                await ws.send_str(_KEEPALIVE_FRAME)
            except (aiohttp.ClientError, ConnectionError):
                return
            if time.monotonic() - self._last_inbound > self._keepalive_interval * _SILENT_INTERVALS:
                # Closing ends the reader, so run() redials with the usual backoff.
                log.warning("сервер молчит дольше %.0f с; переподключаемся", self._keepalive_interval * _SILENT_INTERVALS)
                await ws.close()
                return

    def _on_frame(self, text: str) -> None:
        try:
            frame = decode(text)
        except ProtocolError as exc:
            log.warning("кадр отброшен: %s", exc)
            return
        kind = frame_type(frame)
        rid = frame.get("rid")
        if kind == "Error":
            self._on_error_frame(frame, rid)
            return
        if isinstance(rid, str):
            future = self._pending.pop(rid, None)
            if future is not None:
                if not future.done():
                    future.set_result(frame)
                return
        if kind.endswith("Response"):
            return  # ответ на запрос, который уже перестали ждать
        try:
            event = parse_event(frame)
        except ProtocolError as exc:
            log.warning("событие %s отброшено: %s", kind, exc)
            return
        if event is None:
            log.debug("кадр %s пропущен", kind)
            return
        if self._on_arrival is not None:
            # До очереди: обработчик, который ждёт событие, сам держит диспетчер,
            # поэтому нужное ему событие в очереди никогда бы до него не дошло.
            try:
                self._on_arrival(event)
            except Exception:
                log.exception("необработанная ошибка в хуке прихода события")
        self._enqueue(event)

    def _on_error_frame(self, frame: Frame, rid: object) -> None:
        text = error_text(frame)
        if isinstance(rid, str):
            future = self._pending.pop(rid, None)
            if future is not None:
                if not future.done():
                    future.set_exception(ResponseError(text))
                return
        if wants_no_reconnect(frame):
            raise ConnectionRefused(text, do_not_reconnect=True)
        log.warning("сервер: %s", text)

    # ---- очереди --------------------------------------------------------------

    def _enqueue(self, item: _QueueItem) -> None:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self._queue.get_nowait()
            self._queue.put_nowait(item)
            self.dropped_events += 1
            if self.dropped_events == 1 or self.dropped_events % 1000 == 0:
                log.warning("обработчики не успевают: отброшено событий — %d", self.dropped_events)

    async def _dispatch(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                if isinstance(item, SessionMetadata):
                    await self._on_session(item)
                else:
                    await self._on_event(item)
            except Exception:
                log.exception("необработанная ошибка в обработчике бота")

    def _fail_pending(self, message: str) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(NotConnected(message))
        self._pending.clear()
