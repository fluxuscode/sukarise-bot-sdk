"""Всё, что бот умеет делать: каждый метод :class:`BotAPI` — один запрос к серверу.

Аргументы проверяются до отправки, поэтому ошибка вызывает :class:`InvalidArgument`
в том месте вашего кода, где она допущена, а не отказ сервера позже. Длинный
текст чата и личных сообщений SDK режет на несколько сообщений вместо отказа.

Методы сгруппированы по смыслу: чат, язык тела, движение, комната и модерация,
чаевые и личные сообщения, кошелёк и гардероб.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from . import protocol
from .engine import Requester
from .errors import InvalidArgument
from .outfit import outfit_problems
from .models import (
    FACINGS,
    GOLD_BARS,
    MODERATION_ACTIONS,
    REACTIONS,
    AnchorPosition,
    ConversationPage,
    CurrencyItem,
    DirectMessage,
    GoldBar,
    Item,
    ModerationAction,
    Position,
    Reaction,
    RoomPermissions,
    RoomUser,
)

CHAT_LIMIT = 500
"""Наибольшая длина одной реплики чата в символах; длиннее — режется на части."""
MESSAGE_LIMIT = 1000
"""Наибольшая длина одного личного сообщения в символах."""
BULK_RECIPIENTS = 100
"""Наибольшее число получателей в :meth:`BotAPI.send_bulk_message`."""
CHANNEL_BYTES = 1024
"""Наибольший размер сообщения канала в байтах (UTF-8)."""
CHANNEL_TAGS = 10
"""Наибольшее число меток у сообщения канала."""
CHANNEL_TAG_LENGTH = 32
"""Наибольшая длина одной метки в символах."""
CHANNEL_RECIPIENTS = 50
"""Наибольшее число адресатов у сообщения канала."""
COORDINATE_LIMIT = 1000.0
"""Координаты допустимы в пределах ±этого значения."""
MAX_MODERATION_SECONDS = 30 * 24 * 3600
"""Наибольший срок блокировки или заглушки: 30 суток в секундах."""
GOLD = "gold"
"""Название золота в кошельке (поле ``type`` у :class:`CurrencyItem`)."""


def split_message(text: str, limit: int = CHAT_LIMIT) -> list[str]:
    """Разрезать текст на куски не длиннее ``limit`` символов, по возможности по пробелам.

    Пробелы на стыках отбрасываются, пустой текст даёт пустой список. Если в
    пределах ``limit`` нет ни одного пробела, слово режется ровно по ``limit``.
    Так же :meth:`BotAPI.chat` и :meth:`BotAPI.send_message` делят длинный текст.

    :param text: исходный текст.
    :param limit: наибольшая длина куска; по умолчанию 500 (:data:`CHAT_LIMIT`).
    :returns: список кусков в исходном порядке.
    """
    chunks: list[str] = []
    rest = text.strip()
    while len(rest) > limit:
        cut = rest.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks


def _non_empty(value: str, what: str) -> str:
    if not value.strip():
        raise InvalidArgument(f"{what}: значение не может быть пустым")
    return value


def _check_position(position: Position) -> None:
    if position.facing not in FACINGS:
        raise InvalidArgument(f"неизвестное направление взгляда {position.facing!r}")
    for axis, value in (("x", position.x), ("y", position.y), ("z", position.z)):
        if not math.isfinite(value) or abs(value) > COORDINATE_LIMIT:
            raise InvalidArgument(f"координата {axis} должна быть конечным числом в пределах ±{COORDINATE_LIMIT:g}")


class BotAPI:
    """Действия бота: чат, движение, модерация, чаевые, личные сообщения, кошелёк, наряд.

    Объект не создают вручную: в работающем боте он доступен как ``self.api``
    (а в команде — ещё и как ``ctx.api``). Каждый метод — одна асинхронная
    операция, которую нужно ждать через ``await``.

    **Общие исключения.** Любой метод может выбросить:

    * :class:`NotConnected` — у бота нет соединения;
    * :class:`RequestTimeout` — сервер не ответил за 10 секунд;
    * :class:`ResponseError` — сервер отказал в запросе (прав нет, пользователя нет в
      комнате, действие не поддерживается в 3D-комнате и т. п.);
    * :class:`InvalidArgument` — аргумент неверен, запрос не отправлялся.

    **Лимиты.** Сервер ограничивает частоту запросов по категориям (``chat``,
    ``move``, ``info`` и др.). SDK ведёт такие же счётчики и при превышении
    сам ждёт своей очереди, так что отказа по лимиту бот обычно не видит.

    **2D и 3D.** Бот работает и в обычных (2D), и в 3D-комнатах. В 3D-комнате
    доступны чат, шёпот, ходьба, список людей, личные сообщения и всё, что связано
    с аккаунтом бота (кошелёк, гардероб, наряд, покупки); эмоции, реакции, посадка,
    телепорт, модерация и чаевые там отказывают с :class:`ResponseError`.
    """

    def __init__(self, requester: Requester) -> None:
        """Создать набор действий поверх канала запросов.

        :param requester: то, что отправляет запрос и возвращает ответ: в работе
            это соединение с сервером, в тестах — запись запросов
            (:class:`sukarisebot.RecordingRequester`).
        """
        self._requester = requester

    # ---- чат ------------------------------------------------------------------

    async def chat(self, message: str) -> None:
        """Сказать фразу в общий чат комнаты.

        Текст длиннее 500 символов режется по пробелам и уходит несколькими
        сообщениями подряд.

        Запрос ``ChatRequest``, категория лимита ``chat``. Комнаты: 2D и 3D.

        :param message: текст реплики.
        :raises InvalidArgument: текст пустой или состоит из пробелов.
        :raises ResponseError: сервер отказал (например, бота заглушили).
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        chunks = split_message(message)
        if not chunks:
            raise InvalidArgument("сообщение пусто")
        for chunk in chunks:
            await self._requester.request("ChatRequest", "chat", {"message": chunk, "whisper_target_id": None})

    async def whisper(self, user_id: str, message: str) -> None:
        """Отправить личное сообщение одному человеку в комнате (шёпот).

        Шёпот видят только получатель и бот. Текст длиннее 500 символов режется
        на несколько шёпотов.

        Запрос ``ChatRequest`` с адресатом, категория лимита ``chat``.
        Комнаты: 2D и 3D.

        :param user_id: идентификатор получателя; он должен быть в комнате.
        :param message: текст шёпота.
        :raises InvalidArgument: текст или идентификатор пусты.
        :raises ResponseError: получателя нет в комнате или сервер отказал иначе.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        chunks = split_message(message)
        if not chunks:
            raise InvalidArgument("сообщение пусто")
        target = _non_empty(user_id, "ID пользователя")
        for chunk in chunks:
            await self._requester.request("ChatRequest", "chat", {"message": chunk, "whisper_target_id": target})

    async def channel(
        self,
        message: str,
        *,
        tags: Iterable[str] = (),
        only_to: Iterable[str] | None = None,
    ) -> None:
        """Отправить скрытое сообщение другим ботам в этой комнате.

        Игроки его не видят. Получатели услышат его в :meth:`Bot.on_channel`.
        Так боты в одной комнате могут договариваться между собой. Сам отправитель
        своё сообщение не получает.

        Запрос ``ChannelRequest``, категория лимита ``channel``. Комнаты: 2D и 3D.

        :param message: текст, не больше 1024 байт в UTF-8.
        :param tags: метки (до 10 штук по 32 символа), по ним получатели отбирают сообщения.
        :param only_to: идентификаторы ботов-адресатов (до 50); ``None`` — всем ботам комнаты.
        :raises InvalidArgument: текст пуст или слишком велик, меток или адресатов слишком много.
        :raises ResponseError: сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        text = _non_empty(message, "сообщение канала")
        if len(text.encode()) > CHANNEL_BYTES:
            raise InvalidArgument(f"сообщение канала длиннее {CHANNEL_BYTES} байт")
        tag_list = list(tags)
        if len(tag_list) > CHANNEL_TAGS or any(len(tag) > CHANNEL_TAG_LENGTH for tag in tag_list):
            raise InvalidArgument(f"меток не больше {CHANNEL_TAGS}, длина метки не больше {CHANNEL_TAG_LENGTH} символов")
        recipients = None if only_to is None else list(only_to)
        if recipients is not None and len(recipients) > CHANNEL_RECIPIENTS:
            raise InvalidArgument(f"адресатов не больше {CHANNEL_RECIPIENTS}")
        await self._requester.request(
            "ChannelRequest",
            "channel",
            {"message": text, "tags": tag_list, "only_to": recipients},
        )

    # ---- язык тела ------------------------------------------------------------

    async def emote(self, emote_id: str, *, target_user_id: str | None = None) -> None:
        """Сыграть эмоцию: самому или в сторону другого человека.

        Платные эмоции бот может играть бесплатно, если у его владельца активный
        PREMIUM. Парные эмоции (с партнёром) боту недоступны.

        Запрос ``EmoteRequest``, категория лимита ``emote``. Комнаты: только 2D.

        :param emote_id: идентификатор эмоции, например ``"emote-wave"``.
        :param target_user_id: на кого направлена эмоция; ``None`` — ни на кого.
        :raises InvalidArgument: идентификатор эмоции пуст.
        :raises ResponseError: эмоции нет, она парная или платная без PREMIUM у
            владельца, или комната 3D.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        await self._requester.request(
            "EmoteRequest",
            "emote",
            {"emote_id": _non_empty(emote_id, "ID эмоции"), "target_user_id": target_user_id},
        )

    async def react(self, reaction: Reaction, target_user_id: str) -> None:
        """Отправить человеку реакцию: ``clap``, ``heart``, ``thumbs``, ``wave`` или ``wink``.

        Запрос ``ReactionRequest``, категория лимита ``emote``. Комнаты: только 2D.

        :param reaction: одна из пяти реакций (см. :data:`Reaction`).
        :param target_user_id: кому отправить; человек должен быть в комнате.
        :raises InvalidArgument: неизвестная реакция или пустой идентификатор.
        :raises ResponseError: адресата нет в комнате или комната 3D.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        if reaction not in REACTIONS:
            raise InvalidArgument(f"неизвестная реакция {reaction!r}")
        await self._requester.request(
            "ReactionRequest",
            "emote",
            {"reaction": reaction, "target_user_id": _non_empty(target_user_id, "ID пользователя")},
        )

    # ---- движение -------------------------------------------------------------

    async def move_to(self, position: Position) -> None:
        """Отправить бота пешком в точку на полу.

        Запрос ``FloorHitRequest``, категория лимита ``move``. Комнаты: 2D и 3D.

        :param position: целевая точка; координаты — конечные числа в пределах ±1000.
        :raises InvalidArgument: координата вне диапазона или неизвестное направление.
        :raises ResponseError: точка недоступна.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        _check_position(position)
        await self._requester.request(
            "FloorHitRequest",
            "move",
            {"destination": protocol.position_body(position)},
        )

    async def sit_on(self, anchor: AnchorPosition) -> None:
        """Посадить бота на место предмета мебели.

        Место (``entity_id`` и ``anchor_ix``) берите из положения человека, который
        на этой мебели сидит: у сидящего ``location`` — это :class:`AnchorPosition`.

        Запрос ``AnchorHitRequest``, категория лимита ``move``. Комнаты: только 2D.

        :param anchor: предмет мебели и номер места на нём.
        :raises InvalidArgument: пустой идентификатор предмета.
        :raises ResponseError: места нет, оно занято или комната 3D.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        await self._requester.request(
            "AnchorHitRequest",
            "move",
            {"anchor": {"entity_id": _non_empty(anchor.entity_id, "ID предмета мебели"), "anchor_ix": anchor.anchor_ix}},
        )

    async def teleport_user(self, user_id: str, position: Position) -> None:
        """Мгновенно переместить любого человека в комнате в точку на полу.

        Нужны права модератора в комнате (право «дизайнер» без модератора не
        подходит). Бот подчиняется тем же правилам, что и человек-модератор.

        Запрос ``TeleportRequest``, категория лимита ``teleport``. Комнаты: только 2D.

        :param user_id: кого переместить.
        :param position: куда; координаты — конечные числа в пределах ±1000.
        :raises InvalidArgument: пустой идентификатор или неверная точка.
        :raises ResponseError: у бота нет прав модератора, человека нет в комнате или комната 3D.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        _check_position(position)
        await self._requester.request(
            "TeleportRequest",
            "teleport",
            {"user_id": _non_empty(user_id, "ID пользователя"), "destination": protocol.position_body(position)},
        )

    # ---- комната --------------------------------------------------------------

    async def list_room_users(self) -> list[RoomUser]:
        """Узнать, кто сейчас в комнате и где стоит или сидит.

        Список включает и самого бота. Обычно вызывать его вручную не нужно:
        состав комнаты ведёт ``bot.room`` (см. :class:`Room`).

        Запрос ``GetRoomUsersRequest``, категория лимита ``info``. Комнаты: 2D и 3D.

        :returns: все, кто в комнате, с их положением.
        :raises ResponseError: сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        frame = await self._requester.request("GetRoomUsersRequest", "info", {})
        return protocol.room_users(frame)

    async def privileges(self, user_id: str) -> RoomPermissions:
        """Узнать, модератор или дизайнер ли человек в этой комнате.

        Запрос ``GetRoomPrivilegeRequest``, категория лимита ``info``. Комнаты: 2D и 3D.

        :param user_id: чьи права проверить.
        :returns: права; ``None`` в поле означает, что сервер не сообщил.
        :raises InvalidArgument: пустой идентификатор.
        :raises ResponseError: сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        frame = await self._requester.request(
            "GetRoomPrivilegeRequest",
            "info",
            {"user_id": _non_empty(user_id, "ID пользователя")},
        )
        return protocol.permissions(frame)

    async def set_privileges(
        self,
        user_id: str,
        *,
        moderator: bool | None = None,
        designer: bool | None = None,
    ) -> None:
        """Выдать или отобрать права модератора и дизайнера.

        .. note::
           Сервер SukaRise не позволяет ботам менять права в комнате: это могут
           только владелец и персонал. Вызов всегда заканчивается
           :class:`ResponseError`. Метод оставлен для совместимости с кодом,
           написанным под официальный SDK Highrise.

        Запрос ``ChangeRoomPrivilegeRequest``, категория лимита ``moderate``.

        :param user_id: чьи права меняются.
        :param moderator: ``True`` — выдать, ``False`` — отобрать, ``None`` — не менять.
        :param designer: то же для права дизайнера.
        :raises InvalidArgument: пустой идентификатор.
        :raises ResponseError: всегда на сервере SukaRise.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        await self._requester.request(
            "ChangeRoomPrivilegeRequest",
            "moderate",
            {
                "user_id": _non_empty(user_id, "ID пользователя"),
                "permissions": {"moderator": moderator, "designer": designer},
            },
        )

    async def moderate(self, user_id: str, action: ModerationAction, *, seconds: int | None = None) -> None:
        """Выгнать, заблокировать, разблокировать или заглушить человека в комнате.

        У бота должны быть права **модератора** в комнате. Бот, у которого только
        право «дизайнер» (его достаточно, чтобы войти), модерировать не может.
        Бот подчиняется тем же правилам, что и человек: например, нельзя наказать
        владельца комнаты. Проще всего пользоваться короткими методами
        :meth:`kick`, :meth:`ban`, :meth:`unban` и :meth:`mute`.

        Запрос ``ModerateRoomRequest``, категория лимита ``moderate``. Комнаты: только 2D.

        :param user_id: к кому применить действие.
        :param action: ``"kick"``, ``"ban"``, ``"unban"`` или ``"mute"``.
        :param seconds: срок блокировки или заглушки в секундах, до 30 суток
            (2 592 000); ``None`` — срок не задан, и сервер решает сам.
        :raises InvalidArgument: неизвестное действие, срок вне диапазона или пустой идентификатор.
        :raises ResponseError: нет прав модератора, цель защищена (владелец комнаты,
            а для не-владельца ещё и другие модераторы), или комната 3D.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        if action not in MODERATION_ACTIONS:
            raise InvalidArgument(f"неизвестное действие модерации {action!r}")
        if seconds is not None and not 0 <= seconds <= MAX_MODERATION_SECONDS:
            raise InvalidArgument(f"срок должен быть от 0 до {MAX_MODERATION_SECONDS} секунд")
        await self._requester.request(
            "ModerateRoomRequest",
            "moderate",
            {"user_id": _non_empty(user_id, "ID пользователя"), "moderation_action": action, "action_length": seconds},
        )

    async def kick(self, user_id: str) -> None:
        """Выгнать человека из комнаты. То же, что ``moderate(user_id, "kick")``.

        Нужны права модератора. Комнаты: только 2D. Исключения — как у :meth:`moderate`.

        :param user_id: кого выгнать.
        """
        await self.moderate(user_id, "kick")

    async def ban(self, user_id: str, *, seconds: int | None = None) -> None:
        """Заблокировать человека в комнате. То же, что ``moderate(user_id, "ban")``.

        Нужны права модератора. Комнаты: только 2D. Исключения — как у :meth:`moderate`.

        :param user_id: кого заблокировать.
        :param seconds: срок в секундах (до 30 суток); ``None`` — срок не задан, и сервер решает сам.
        """
        await self.moderate(user_id, "ban", seconds=seconds)

    async def unban(self, user_id: str) -> None:
        """Снять блокировку или заглушку. То же, что ``moderate(user_id, "unban")``.

        Нужны права модератора. Комнаты: только 2D. Исключения — как у :meth:`moderate`.

        :param user_id: с кого снять.
        """
        await self.moderate(user_id, "unban")

    async def mute(self, user_id: str, seconds: int) -> None:
        """Заглушить человека на срок. То же, что ``moderate(user_id, "mute", seconds=...)``.

        Заглушенный не может писать в чат. Нужны права модератора. Комнаты:
        только 2D. Исключения — как у :meth:`moderate`.

        :param user_id: кого заглушить.
        :param seconds: на сколько секунд (до 30 суток).
        """
        await self.moderate(user_id, "mute", seconds=seconds)

    # ---- чаевые, покупки и личные сообщения ------------------------------------

    async def tip(self, user_id: str, gold_bar: GoldBar) -> bool:
        """Дать человеку в комнате чаевые слитком золота из кошелька бота.

        Отправитель платит чуть больше, чем получает адресат (11 золота за
        ``gold_bar_10``). Нехватка золота — это ответ, а не ошибка: метод
        возвращает ``False`` и ничего не списывает.

        Запрос ``TipUserRequest``, категория лимита ``tip``. Комнаты: только 2D.

        :param user_id: кому дать чаевые; он должен быть в комнате.
        :param gold_bar: слиток (см. :data:`GoldBar`).
        :returns: ``True`` — чаевые отправлены, ``False`` — у бота не хватает золота.
        :raises InvalidArgument: неизвестный слиток или пустой идентификатор.
        :raises ResponseError: адресата нет в комнате или комната 3D.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        if gold_bar not in GOLD_BARS:
            raise InvalidArgument(f"неизвестный слиток золота {gold_bar!r}")
        frame = await self._requester.request(
            "TipUserRequest",
            "tip",
            {"user_id": _non_empty(user_id, "ID пользователя"), "gold_bar": gold_bar},
        )
        return protocol.paid(frame)

    async def buy_item(self, item_id: str) -> bool:
        """Купить один предмет в магазине за золото из кошелька бота.

        Ботам продаются только предметы, которые магазин продаёт за золото.
        Купленный предмет становится вещью бота и появляется в :meth:`inventory`.
        Нехватка золота — это ответ, а не ошибка: метод возвращает ``False``.

        Запрос ``BuyItemRequest``, категория лимита ``shop``. Комнаты: 2D и 3D.

        :param item_id: идентификатор предмета из каталога.
        :returns: ``True`` — куплено, ``False`` — не хватило золота.
        :raises InvalidArgument: пустой идентификатор.
        :raises ResponseError: предмета нет в каталоге или магазин продаёт его не за золото.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        frame = await self._requester.request("BuyItemRequest", "shop", {"item_id": _non_empty(item_id, "ID предмета")})
        return protocol.paid(frame)

    async def conversations(self, *, not_joined: bool = False, last_id: str | None = None) -> ConversationPage:
        """Получить личные диалоги бота, по 20 штук за раз.

        Запрос на диалог принимается за бота в момент прихода, поэтому
        ``not_joined`` обычно пуст. Для следующей страницы передайте в ``last_id``
        идентификатор последнего диалога текущей.

        Запрос ``GetConversationsRequest``, категория лимита ``info``.
        Комнаты: 2D и 3D.

        :param not_joined: ``True`` — вместо принятых показать ещё не принятые.
        :param last_id: идентификатор диалога, после которого продолжить.
        :returns: страница диалогов.
        :raises ResponseError: сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        frame = await self._requester.request(
            "GetConversationsRequest", "info", {"not_joined": not_joined, "last_id": last_id}
        )
        return protocol.conversations(frame)

    async def messages(self, conversation_id: str, *, last_message_id: str | None = None) -> list[DirectMessage]:
        """Прочитать сообщения диалога, новые первыми, по 20 штук за раз.

        Чтение новейшей страницы отмечает диалог прочитанным. Чтобы пойти
        дальше в прошлое, передайте идентификатор самого старого сообщения из
        имеющихся в ``last_message_id``.

        Запрос ``GetMessagesRequest``, категория лимита ``info``. Комнаты: 2D и 3D.

        :param conversation_id: диалог (приходит в :class:`MessageEvent`).
        :param last_message_id: идентификатор сообщения, раньше которого читать.
        :returns: до 20 сообщений, самое новое первым.
        :raises InvalidArgument: пустой идентификатор диалога.
        :raises ResponseError: диалога нет или бот в нём не участвует.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        frame = await self._requester.request(
            "GetMessagesRequest",
            "info",
            {"conversation_id": _non_empty(conversation_id, "ID диалога"), "last_message_id": last_message_id},
        )
        return protocol.messages(frame)

    async def send_message(self, conversation_id: str, content: str) -> None:
        """Ответить в личном диалоге, в котором бот уже участвует.

        Бот отвечает, а не начинает разговор: первым пишет человек. Текст длиннее
        1000 символов режется на несколько сообщений. Отправляется только текст.

        Запрос ``SendMessageRequest``, категория лимита ``message``. Комнаты: 2D и 3D.

        :param conversation_id: диалог, в который ответить.
        :param content: текст ответа.
        :raises InvalidArgument: пустой диалог или текст.
        :raises ResponseError: бот в диалоге не участвует или сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        _non_empty(conversation_id, "ID диалога")
        for chunk in split_message(_non_empty(content, "сообщение"), MESSAGE_LIMIT):
            await self._requester.request(
                "SendMessageRequest",
                "message",
                {"conversation_id": conversation_id, "content": chunk, "type": "text"},
            )

    async def send_bulk_message(self, user_ids: Sequence[str], content: str) -> None:
        """Написать до 100 людям, с которыми у бота уже есть личный диалог.

        Тем, кто боту ещё не писал, сообщение не уходит. Если оно не дошло ни до
        кого, сервер отказывает. Сообщение должно уложиться в 1000 символов:
        здесь текст не режется.

        Запрос ``SendBulkMessageRequest``, категория лимита ``message``.
        Комнаты: 2D и 3D.

        :param user_ids: получатели, от 1 до 100.
        :param content: текст, не длиннее 1000 символов.
        :raises InvalidArgument: список пуст или длиннее 100, текст пуст или слишком длинный.
        :raises ResponseError: сообщение не дошло ни до кого.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        if not user_ids or len(user_ids) > BULK_RECIPIENTS:
            raise InvalidArgument(f"получателей должно быть от 1 до {BULK_RECIPIENTS}")
        text = _non_empty(content, "сообщение").strip()
        if len(text) > MESSAGE_LIMIT:
            raise InvalidArgument(f"сообщение длиннее {MESSAGE_LIMIT} символов")
        await self._requester.request(
            "SendBulkMessageRequest",
            "message",
            {"user_ids": [_non_empty(user_id, "ID пользователя") for user_id in user_ids], "content": text, "type": "text"},
        )

    async def leave_conversation(self, conversation_id: str) -> None:
        """Выйти из личного диалога.

        Запрос ``LeaveConversationRequest``, категория лимита ``message``.
        Комнаты: 2D и 3D.

        :param conversation_id: диалог, из которого выйти.
        :raises InvalidArgument: пустой идентификатор.
        :raises ResponseError: диалога нет или бот в нём не участвует.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        await self._requester.request(
            "LeaveConversationRequest",
            "message",
            {"conversation_id": _non_empty(conversation_id, "ID диалога")},
        )

    # ---- кошелёк, гардероб и инвентарь ------------------------------------------

    async def wallet(self) -> list[CurrencyItem]:
        """Получить все валюты бота и их количество.

        Запрос ``GetWalletRequest``, категория лимита ``info``. Комнаты: 2D и 3D.

        :returns: список валют; золото — элемент с ``type == "gold"``.
        :raises ResponseError: сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        frame = await self._requester.request("GetWalletRequest", "info", {})
        return protocol.currencies(frame)

    async def gold(self) -> int:
        """Получить количество золота у бота (0, если золота нет).

        Удобная обёртка над :meth:`wallet`. Золото бот получает чаевыми; владелец
        забирает его себе в личном кабинете.

        :returns: золото бота.
        :raises ResponseError: сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        for currency in await self.wallet():
            if currency.type == GOLD:
                return currency.amount
        return 0

    async def outfit_of(self, user_id: str) -> list[Item]:
        """Узнать, во что сейчас одет человек (или сам бот).

        Запрос ``GetUserOutfitRequest``, категория лимита ``info``. Комнаты: 2D и 3D.

        :param user_id: чей наряд посмотреть.
        :returns: надетые предметы.
        :raises InvalidArgument: пустой идентификатор.
        :raises ResponseError: пользователя нет или сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        frame = await self._requester.request(
            "GetUserOutfitRequest",
            "info",
            {"user_id": _non_empty(user_id, "ID пользователя")},
        )
        return protocol.outfit(frame)

    async def inventory(self) -> list[Item]:
        """Получить одежду, которой владеет бот.

        Запрос ``GetInventoryRequest``, категория лимита ``info``. Комнаты: 2D и 3D.

        :returns: предметы гардероба бота.
        :raises ResponseError: сервер отказал.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        frame = await self._requester.request("GetInventoryRequest", "info", {})
        return protocol.inventory(frame)

    async def wear(self, items: Sequence[Item]) -> None:
        """Заменить наряд бота целиком.

        Наряд сначала проверяется на стороне SDK (см. :func:`outfit_problems`):
        тело должно быть закрыто, части тела на месте, а каждая базовая категория
        встречается один раз. Затем наряд проверяет сервер. Пока у владельца бота
        активный PREMIUM, смена наряда бесплатна: бот может надеть любую вещь
        каталога, покупать её не нужно. Чтобы бот надел наряд владельца, владелец
        пишет ему ``myoutfit`` в чат или шёпотом.

        Запрос ``SetOutfitRequest``, категория лимита ``info``. Комнаты: 2D и 3D.

        :param items: полный наряд из одежды (``type == "clothing"``), от 1 до 64 предметов.
        :raises InvalidArgument: наряд нарушает правила (причины перечислены в тексте ошибки).
        :raises ResponseError: у владельца бота нет активного PREMIUM или в наряде есть вещь,
            которой нет в каталоге.
        :raises NotConnected: нет соединения.
        :raises RequestTimeout: сервер не ответил.
        """
        problems = outfit_problems(items)
        if problems:
            raise InvalidArgument("; ".join(problems))
        await self._requester.request(
            "SetOutfitRequest",
            "info",
            {"outfit": [protocol.item_body(item) for item in items]},
        )
