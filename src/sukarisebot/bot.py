"""Бот: наследуйте :class:`Bot`, переопределите нужные обработчики и запустите.

Обработчик — это метод ``async def on_...``. По умолчанию он ничего не делает,
поэтому бот переопределяет только то, что ему нужно. SDK подписывается ровно на
те события, для которых есть переопределённый обработчик, так что лишний трафик
до бота не доходит.

Кроме обработчиков у бота есть команды чата (``@command``), таймеры (``@every``),
ожидание ответа (``await bot.wait_for``), свободный словарь состояния
(``bot.state``, ``bot.user_state``) и состав комнаты (``bot.room``).
"""

# Модуль работает с внутренними (с подчёркиванием) членами других классов пакета.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, cast

import aiohttp

from .api import BotAPI
from .commands import Command, CommandHandler, Commands, Context, Phrases
from .decorators import COMMAND_MARK, EVERY_MARK, CommandSpec
from .engine import DEFAULT_URL, Engine, Requester
from .errors import InvalidArgument, NotConnected
from .models import (
    ChannelEvent,
    CurrencyItem,
    Item,
    ChatEvent,
    EmoteEvent,
    Event,
    Location,
    MessageEvent,
    ModerationEvent,
    ReactionEvent,
    SessionMetadata,
    TipEvent,
    User,
    UserJoinedEvent,
    UserLeftEvent,
    UserMovedEvent,
)
from .room import Room

log = logging.getLogger("sukarisebot")

ENV_TOKEN: Final = "SUKARISEBOT_TOKEN"
"""Переменная окружения с токеном бота (``srbot_…``)."""
ENV_ROOM_ID: Final = "SUKARISEBOT_ROOM_ID"
"""Переменная окружения с идентификатором комнаты."""
ENV_URL: Final = "SUKARISEBOT_URL"
"""Переменная окружения с адресом шлюза; если её нет, берётся :data:`DEFAULT_URL`."""

type PeriodicHandler = Callable[[], Awaitable[None]]
"""Метод-таймер: без аргументов, ничего не возвращает."""
type _Waiter = tuple[Callable[[Event], bool], asyncio.Future[Event]]

# Название обработчика -> подписка, которая нужна серверу, чтобы доставлять его события.
_SUBSCRIPTION_OF: Final[dict[str, str]] = {
    "on_chat": "chat",
    "on_whisper": "chat",
    "on_emote": "emote",
    "on_reaction": "reaction",
    "on_user_join": "user_joined",
    "on_user_leave": "user_left",
    "on_user_move": "user_moved",
    "on_channel": "channel",
    "on_moderate": "moderation",
    "on_tip": "tip_reaction",
    "on_message": "message",
}


@dataclass(frozen=True, slots=True)
class _Schedule:
    seconds: float
    handler: PeriodicHandler


class Bot:
    """Базовый класс любого бота SukaRise.

    Наследуйте его, переопределите нужные обработчики ``on_...`` и запустите бота
    методом :meth:`start` (блокирующий вызов для скриптов) или :meth:`run`
    (корутина для своего цикла событий)::

        from sukarisebot import Bot, Location, User

        class Greeter(Bot):
            async def on_user_join(self, user: User, position: Location) -> None:
                await self.api.chat(f"Добро пожаловать, {user.username}!")

        Greeter().start(token="srbot_...", room_id="room-...")

    **Что есть у бота.**

    * ``self.api`` — действия: чат, движение, модерация, чаевые и т. д. (:class:`BotAPI`);
    * ``self.room`` — кто сейчас в комнате (:class:`Room`);
    * ``self.session`` — кто бот и в какой он комнате (:class:`SessionMetadata`);
    * ``self.state`` — свободный словарь для данных бота, живёт до остановки;
    * ``self.user_state(user_id)`` — свободный словарь на каждого игрока;
    * ``self.http`` — общий HTTP-клиент для запросов к другим сервисам;
    * ``self.wait_for(...)`` — дождаться ответного события в диалоге.

    **Как обрабатываются события.** События доходят до обработчиков по одному,
    в порядке прихода: пока один обработчик не завершился, следующий не
    начнётся. Долгий обработчик задерживает все события после него, поэтому
    долгую работу выносите в ``asyncio.create_task``. Исключение внутри
    обработчика не останавливает бота: оно передаётся в :meth:`on_error`.

    **Подписки.** SDK просит у сервера только те события, для которых в классе
    переопределён обработчик (плюс чат, нужный командам). Это относится и к
    ``bot.room``: см. :class:`Room`.

    :cvar phrases: фразы бота при работе с командами (отказ, «подождите», ``!help``).
    :ivar room: состав комнаты, который SDK ведёт по событиям.
    :ivar state: свободный словарь состояния бота.
    """

    phrases: Phrases = Phrases()
    """Фразы бота при работе с командами. Замените в своём классе, чтобы изменить язык или тон."""

    def __init__(self) -> None:
        """Создать бота. Подключения нет, пока не вызван :meth:`run` или :meth:`start`.

        Если вы переопределяете ``__init__``, первой строкой вызовите
        ``super().__init__()``: иначе команды и таймеры не будут найдены.
        """
        self.room = Room()
        """Состав комнаты: кто здесь и где стоит (см. :class:`Room`)."""
        self.state: dict[str, object] = {}
        """Свободный словарь для данных бота. Живёт, пока работает процесс; не сохраняется на диск."""
        self._commands = Commands(phrases=self.phrases)
        self._session: SessionMetadata | None = None
        self._api: BotAPI | None = None
        self._engine: Engine | None = None
        self._clean_room = False
        self._waiters: list[_Waiter] = []
        self._schedules: list[_Schedule] = []
        self._tasks: list[asyncio.Task[None]] = []
        self._user_state: dict[str, dict[str, object]] = {}
        self._http: aiohttp.ClientSession | None = None
        self._install_marked_methods()

    # ---- что бот знает о себе --------------------------------------------------

    @property
    def session(self) -> SessionMetadata | None:
        """Последняя известная сессия (кто бот, в какой он комнате, какие лимиты).

        ``None`` — до первого подключения и после остановки бота. Во время
        переподключения сохраняет прежнее значение: события, уже стоящие в очереди
        обработчиков, должны видеть, кто бот. Жив ли канал связи сейчас, показывает
        :attr:`connected`.
        """
        return self._session

    @property
    def connected(self) -> bool:
        """``True``, пока у бота есть живое соединение с комнатой.

        На время переподключения становится ``False``, а после нового подключения
        снова ``True`` (и вызывается :meth:`on_start`).
        """
        if self._engine is not None:
            return self._engine.session is not None
        return self._session is not None

    @property
    def api(self) -> BotAPI:
        """Действия бота (:class:`BotAPI`): ``await self.api.chat("...")``.

        :raises NotConnected: бот не запущен. Пока ``run`` не вызван, действий нет.
        """
        if self._api is None:
            raise NotConnected("бот не запущен: запустите его через run() или start()")
        return self._api

    @property
    def owner_id(self) -> str | None:
        """Идентификатор владельца комнаты или ``None`` до первого подключения."""
        return None if self._session is None else self._session.room_info.owner_id

    def is_owner(self, user: User) -> bool:
        """Проверить, что пользователь — владелец комнаты, в которой работает бот.

        Это владелец *комнаты*, а не владелец бота. Обычно это один и тот же человек,
        но не обязательно.

        :param user: кого проверить.
        :returns: ``True``, если ``user.id`` совпадает с ``owner_id``.
        """
        return user.id == self.owner_id

    @property
    def http(self) -> aiohttp.ClientSession:
        """Общий HTTP-клиент (aiohttp) для запросов к другим сервисам.

        Создаётся при первом обращении и закрывается сам, когда бот
        останавливается. Таймаут одного запроса — 10 секунд. Используйте его
        вместо создания клиента в каждом обработчике.
        """
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0))
        return self._http

    async def my_outfit(self) -> list[Item]:
        """Получить то, во что бот одет сейчас.

        :returns: надетые предметы бота.
        :raises NotConnected: бот не подключён к комнате.
        :raises ResponseError: сервер отказал.
        """
        session = self._session
        if session is None:
            raise NotConnected("бот не подключён к комнате")
        return await self.api.outfit_of(session.user_id)

    def user_state(self, user_id: str) -> dict[str, object]:
        """Получить личный словарь данных о игроке (создаётся при первом обращении).

        Живёт, пока работает процесс; на диск не сохраняется (для постоянных
        данных есть :class:`JsonStore`).

        :param user_id: идентификатор игрока.
        :returns: один и тот же словарь при каждом обращении с этим идентификатором.
        """
        return self._user_state.setdefault(user_id, {})

    # ---- диалоги ---------------------------------------------------------------

    async def wait_for[E: Event](
        self,
        kind: type[E],
        check: Callable[[E], bool] | None = None,
        *,
        timeout: float | None = None,
    ) -> E:
        """Дождаться следующего события нужного типа, которое проходит проверку.

        Для короткого диалога: задали вопрос и ждёте ответ. Ожидание срабатывает
        в момент прихода события, даже если обработчик, который ждёт, сам держит
        очередь событий.

        Событие должно приходить боту: чат доставляется всегда, а для остальных
        событий переопределите соответствующий обработчик (достаточно пустого),
        иначе подписки на него нет и ожидание не закончится.

        **Всегда задавайте ``timeout``.** Пока команда или обработчик ждёт, бот не
        обрабатывает другие события; без таймаута ожидание может не закончиться
        никогда. Если проверка ``check`` выбросит исключение, оно выйдет из
        ``wait_for`` в вашем коде.

        Пример::

            reply = await self.wait_for(
                ChatEvent,
                lambda e: e.whisper and e.user.id == user.id,
                timeout=60,
            )

        :param kind: класс события, например :class:`ChatEvent`.
        :param check: функция, которая решает, подходит ли событие; ``None`` — подходит любое.
        :param timeout: сколько секунд ждать; ``None`` — бесконечно (не рекомендуется).
        :returns: подошедшее событие.
        :raises TimeoutError: время вышло, а подходящего события не было.
        """
        future: asyncio.Future[Event] = asyncio.get_running_loop().create_future()

        def matches(event: Event) -> bool:
            if not isinstance(event, kind):
                return False
            return check is None or check(event)

        waiter: _Waiter = (matches, future)
        self._waiters.append(waiter)
        try:
            event = await asyncio.wait_for(future, timeout)
        finally:
            with contextlib.suppress(ValueError):
                self._waiters.remove(waiter)
        return cast(E, event)

    async def refresh_room(self) -> None:
        """Загрузить с сервера всех, кто в комнате, в ``bot.room``.

        Нужен в режиме «чистой комнаты» и тогда, когда бот не следит за входами
        и выходами через обработчики (см. :class:`Room`).

        :raises NotConnected: бот не запущен.
        :raises ResponseError: сервер отказал.
        """
        self.room._seed(await self.api.list_room_users())

    # ---- запуск ----------------------------------------------------------------

    async def run(
        self,
        *,
        token: str | None = None,
        room_id: str | None = None,
        url: str | None = None,
        clean_room: bool = False,
        reconnect: bool = True,
    ) -> None:
        """Подключиться и работать, пока не вызван :meth:`stop` или сервер не откажет насовсем.

        Без аргументов токен и комната берутся из переменных окружения
        ``SUKARISEBOT_TOKEN`` и ``SUKARISEBOT_ROOM_ID``, а адрес шлюза — из
        ``SUKARISEBOT_URL`` (если её нет, используется :data:`DEFAULT_URL`).

        При потере связи бот подключается заново (``reconnect=True``) с растущей
        паузой до 30 секунд; при каждом новом подключении вызывается
        :meth:`on_start`. Временный отказ сервера (например, у владельца бота
        закончился PREMIUM, или комната ещё не готова) тоже не завершает работу:
        бот повторяет попытку, пока отказ не станет окончательным.

        :param token: токен бота (``srbot_…``) из личного кабинета.
        :param room_id: идентификатор комнаты, в которую должен прийти бот.
        :param url: адрес шлюза (``wss://…/web/botapi``).
        :param clean_room: режим «чистой комнаты»: бот не делает ни одного запроса,
            которого не просил его код, и стартует с пустым составом комнаты;
            ``bot.room`` наполняется по событиям входа, а полный список загружается
            явно через :meth:`refresh_room`.
        :param reconnect: подключаться заново после потери связи и временных отказов.
        :raises InvalidArgument: токен или комната не заданы ни аргументом, ни окружением.
        :raises ConnectionRefused: сервер отказал окончательно (токен отозван,
            бот запущен в другом месте, нет прав в комнате, комнаты нет), либо
            временно при ``reconnect=False``.
        """
        resolved_token = token or os.environ.get(ENV_TOKEN)
        resolved_room = room_id or os.environ.get(ENV_ROOM_ID)
        if not resolved_token or not resolved_room:
            raise InvalidArgument(f"укажите токен и ID комнаты или задайте переменные {ENV_TOKEN} и {ENV_ROOM_ID}")
        engine = Engine(
            url=url or os.environ.get(ENV_URL) or DEFAULT_URL,
            token=resolved_token,
            room_id=resolved_room,
            subscriptions=self._subscriptions(),
            on_session=self._on_session,
            on_event=self._on_event,
            on_arrival=self._on_arrival,
            reconnect=reconnect,
        )
        self._engine = engine
        self._api = BotAPI(engine)
        self._clean_room = clean_room
        try:
            await engine.run()
        finally:
            await self._stop_schedules()
            if self._http is not None:
                await self._http.close()
                self._http = None
            self._session = None
            self._engine = None
            self._api = None

    def start(
        self,
        *,
        token: str | None = None,
        room_id: str | None = None,
        url: str | None = None,
        clean_room: bool = False,
        reconnect: bool = True,
    ) -> None:
        """Запустить бота блокирующим вызовом (для обычных скриптов). Останов — Ctrl+C.

        Создаёт цикл событий (``asyncio.run``) и вызывает в нём :meth:`run`. Если
        у вас уже есть свой цикл событий, используйте :meth:`run`. Аргументы и
        исключения те же, что у :meth:`run`.
        """
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(
                self.run(token=token, room_id=room_id, url=url, clean_room=clean_room, reconnect=reconnect)
            )

    async def stop(self) -> None:
        """Отключить работающего бота. :meth:`run` вернётся, когда сокет закроется.

        Можно вызывать из обработчика или команды. Если бот не запущен, ничего не делает.
        """
        if self._engine is not None:
            await self._engine.stop()

    # ---- обработчики, которые вы переопределяете -----------------------------------

    async def on_start(self, session: SessionMetadata) -> None:
        """Бот вошёл в комнату. Вызывается заново после каждого переподключения.

        Подходит для приветствия, начальной настройки и первого запроса состава.
        К этому моменту ``bot.room`` уже заполнен (кроме режима «чистой комнаты»).

        :param session: кто бот, в какой он комнате и какие у него лимиты.
        """

    async def on_chat(self, user: User, message: str) -> None:
        """Реплика в общем чате комнаты.

        Вызывается для любой реплики, в том числе для сообщений-команд
        (``!команда``): команда выполняется отдельно, после этого обработчика.
        Реплики самого бота в 2D-комнате сервер боту не присылает, а команды,
        написанные самим ботом, SDK не выполняет.

        :param user: кто написал.
        :param message: текст реплики.
        """

    async def on_whisper(self, user: User, message: str) -> None:
        """Личное сообщение (шёпот), отправленное боту в комнате.

        Не путайте с личными сообщениями в диалогах вне комнаты: те приходят в
        :meth:`on_message`.

        :param user: кто прошептал.
        :param message: текст шёпота.
        """

    async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None:
        """Пользователь сыграл эмоцию.

        :param user: кто сыграл.
        :param emote_id: идентификатор эмоции, например ``emote-wave``.
        :param receiver: кому она адресована; ``None``, если ни на кого не направлена.
        """

    async def on_reaction(self, user: User, reaction: str, receiver: User) -> None:
        """Один пользователь отправил другому реакцию.

        :param user: кто отправил.
        :param reaction: ``clap``, ``heart``, ``thumbs``, ``wave`` или ``wink``.
        :param receiver: кому адресована.
        """

    async def on_user_join(self, user: User, position: Location) -> None:
        """В комнату вошёл пользователь.

        Если переопределены ещё ``on_user_leave`` и ``on_user_move``, ``bot.room``
        отражает вход автоматически.

        :param user: кто вошёл.
        :param position: где он появился: :class:`Position` или :class:`AnchorPosition`.
        """

    async def on_user_leave(self, user: User) -> None:
        """Пользователь вышел из комнаты.

        :param user: кто вышел.
        """

    async def on_user_move(self, user: User, position: Location) -> None:
        """Пользователь пошёл в другую точку или сел.

        В оживлённой комнате такие события идут часто; подписывайтесь на них,
        только если они вам нужны.

        :param user: кто переместился.
        :param position: куда: :class:`Position` на полу или :class:`AnchorPosition` на мебели.
        """

    async def on_channel(self, sender_id: str, message: str, tags: tuple[str, ...]) -> None:
        """Скрытое сообщение от другого бота в этой комнате (см. :meth:`BotAPI.channel`).

        Игроки такие сообщения не видят. Собственные сообщения бот не получает.

        :param sender_id: идентификатор бота-отправителя.
        :param message: текст.
        :param tags: метки, которыми отправитель пометил сообщение.
        """

    async def on_moderate(
        self,
        moderator_id: str,
        target_user_id: str,
        moderation_type: str,
        duration: int | None,
    ) -> None:
        """В комнате выполнено действие модерации.

        О действиях, которые бот выполнил сам, он не уведомляется. Если
        наказан сам бот, ``target_user_id`` — это его идентификатор.

        :param moderator_id: кто выполнил действие.
        :param target_user_id: к кому оно применено.
        :param moderation_type: ``kick``, ``ban``, ``unban`` или ``mute``.
        :param duration: срок в секундах или ``None``, если срок не задан.
        """

    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        """Кто-то дал кому-то чаевые.

        Событие приходит о любых чаевых в комнате. Чаевые *боту* — те, у которых
        ``receiver.id == self.session.user_id``. Золото приходит как
        :class:`CurrencyItem` (``item.amount`` — сколько золота получил бот),
        предмет — как :class:`Item`.

        :param sender: кто дал.
        :param receiver: кто получил.
        :param item: что отдано.
        """

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        """Человек написал боту личное сообщение (в диалоге вне комнаты).

        Текст в событии не приходит. Прочитайте его через
        ``await self.api.messages(conversation_id)`` (новые сообщения первыми),
        ответьте через ``await self.api.send_message(conversation_id, "...")``.
        Первым бот в диалог не пишет: начинает человек.

        :param user_id: кто написал.
        :param conversation_id: диалог.
        :param is_new_conversation: ``True``, если это первое сообщение диалога.
        """

    async def on_error(self, error: Exception, event: Event | None) -> None:
        """Обработчик, команда или таймер выбросили исключение. Бот продолжает работать.

        По умолчанию ошибка записывается в журнал ``sukarisebot`` вместе с
        трассировкой. Переопределите метод, чтобы, например, сообщить владельцу.
        Если упадёт и сам ``on_error``, это тоже попадёт в журнал, а бот продолжит.

        :param error: исключение.
        :param event: событие, при обработке которого оно возникло. Для команды
            это событие чата, которое её вызвало; ``None`` — для таймера и для
            ошибки в ``on_start``.
        """
        where = type(event).__name__ if event is not None else "таймер или команда"
        log.error("ошибка в коде бота при обработке %s: %s", where, error, exc_info=error)

    def _install_marked_methods(self) -> None:
        """Зарегистрировать методы, помеченные ``@command`` и ``@every``."""
        for name in dir(type(self)):
            member = inspect.getattr_static(type(self), name, None)
            spec = getattr(member, COMMAND_MARK, None)
            if isinstance(spec, CommandSpec):
                self._commands.add(
                    Command(
                        name=spec.name,
                        handler=cast(CommandHandler, getattr(self, name)),
                        aliases=spec.aliases,
                        description=spec.description,
                        cooldown=spec.cooldown,
                        owner_only=spec.owner_only,
                    )
                )
            interval = getattr(member, EVERY_MARK, None)
            if isinstance(interval, float):
                self._schedules.append(_Schedule(interval, cast(PeriodicHandler, getattr(self, name))))
        if not self._commands.has("help"):
            self._commands.add(Command(name="help", handler=self._show_help, description="список команд"))

    # ---- внутреннее устройство -----------------------------------------------------

    def _attach(self, requester: Requester, session: SessionMetadata, clean_room: bool) -> None:
        """Подключить бота к любому requester, например к тестовому стенду. Вместо run()."""
        self._api = BotAPI(requester)
        self._session = session
        self._clean_room = clean_room

    def _subscriptions(self) -> frozenset[str]:
        cls = type(self)
        wanted = {"chat"}  # команды читают чат, поэтому подписка на чат включена всегда
        for method, subscription in _SUBSCRIPTION_OF.items():
            if getattr(cls, method) is not getattr(Bot, method):
                wanted.add(subscription)
        return frozenset(wanted)

    async def _on_session(self, session: SessionMetadata) -> None:
        self._session = session
        self.room._reset()
        self._start_schedules()
        if not self._clean_room:
            await self._guard(None, self.refresh_room())
        await self._guard(None, self.on_start(session))

    def _on_arrival(self, event: Event) -> None:
        """Событие только что пришло из сокета, раньше обработчиков, ждущих в очереди."""
        self._resolve_waiters(event)

    async def _on_event(self, event: Event) -> None:
        self._track_room(event)
        await self._guard(event, self._route(event))
        if isinstance(event, ChatEvent):
            await self._guard(event, self._run_command(event))

    async def _route(self, event: Event) -> None:
        match event:
            case ChatEvent(user=user, message=message, whisper=True):
                await self.on_whisper(user, message)
            case ChatEvent(user=user, message=message):
                await self.on_chat(user, message)
            case EmoteEvent(user=user, emote_id=emote_id, receiver=receiver):
                await self.on_emote(user, emote_id, receiver)
            case ReactionEvent(user=user, reaction=reaction, receiver=receiver):
                await self.on_reaction(user, reaction, receiver)
            case UserJoinedEvent(user=user, position=position):
                await self.on_user_join(user, position)
            case UserLeftEvent(user=user):
                await self.on_user_leave(user)
            case UserMovedEvent(user=user, position=position):
                await self.on_user_move(user, position)
            case ChannelEvent(sender_id=sender_id, message=message, tags=tags):
                await self.on_channel(sender_id, message, tags)
            case TipEvent(sender=sender, receiver=receiver, item=item):
                await self.on_tip(sender, receiver, item)
            case MessageEvent(user_id=user_id, conversation_id=conversation_id, is_new_conversation=is_new):
                await self.on_message(user_id, conversation_id, is_new)
            case ModerationEvent(
                moderator_id=moderator_id,
                target_user_id=target_user_id,
                moderation_type=moderation_type,
                duration=duration,
            ):
                await self.on_moderate(moderator_id, target_user_id, moderation_type, duration)

    async def _run_command(self, event: ChatEvent) -> None:
        if self._session is not None and event.user.id == self._session.user_id:
            return  # бот никогда не отвечает самому себе
        await self._commands.dispatch(
            self.api,
            event.user,
            event.message,
            whisper=event.whisper,
            is_owner=self.is_owner(event.user),
        )

    async def _show_help(self, context: Context) -> None:
        commands = self._commands
        listing = commands.phrases.help_separator.join(command.usage(commands.prefix) for command in commands.listing())
        await context.reply(commands.phrases.help.format(commands=listing))

    def _track_room(self, event: Event) -> None:
        match event:
            case UserJoinedEvent(user=user, position=position):
                self.room._join(user, position)
            case UserMovedEvent(user=user, position=position):
                self.room._move(user, position)
            case UserLeftEvent(user=user):
                self.room._leave(user.id)
            case _:
                pass

    def _resolve_waiters(self, event: Event) -> None:
        for waiter in list(self._waiters):
            matches, future = waiter
            if future.done():
                continue
            try:
                hit = matches(event)
            except Exception as exc:
                future.set_exception(exc)  # проверка — код вызывающего: он и увидит её сбой
                continue
            if hit:
                future.set_result(event)

    def _start_schedules(self) -> None:
        if self._tasks:
            return
        for schedule in self._schedules:
            self._tasks.append(asyncio.create_task(self._tick(schedule), name=f"sukarisebot-every-{schedule.seconds:g}s"))

    async def _tick(self, schedule: _Schedule) -> None:
        while True:
            await asyncio.sleep(schedule.seconds)
            if self.connected:
                await self._guard(None, schedule.handler())

    async def _stop_schedules(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    async def _guard(self, event: Event | None, work: Awaitable[None]) -> None:
        """Дождаться кода бота. Сбой уходит в ``on_error`` и не останавливает диспетчер."""
        try:
            await work
        except Exception as exc:
            try:
                await self.on_error(exc, event)
            except Exception:
                log.exception("сам on_error завершился ошибкой")
