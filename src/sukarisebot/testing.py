"""Тестирование бота без сервера.

``Harness`` запускает бота в памяти. Подавайте ему события через ``say`` и
``emit``, а потом читайте, что бот попросил сделать у сервера. Сеть не
используется, ждать таймеры не нужно::

    async def test_greeting() -> None:
        harness = Harness(Greeter())
        await harness.start()
        await harness.join("alice")
        assert harness.chats == ["Добро пожаловать, alice!"]

Подробности — в ``docs/testing.md``.
"""

# Модуль работает с внутренними (с подчёркиванием) членами других классов пакета.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from . import protocol
from .bot import Bot
from .errors import ResponseError
from .models import (
    ChatEvent,
    CurrencyItem,
    Event,
    Item,
    Location,
    Position,
    RoomInfo,
    RoomPermissions,
    RoomUser,
    SessionMetadata,
    TipEvent,
    User,
    UserJoinedEvent,
    UserLeftEvent,
)


@dataclass(frozen=True, slots=True)
class Sent:
    """Один запрос, который бот отправил, в том виде, в каком его получил бы сервер.

    :ivar kind: тип запроса, например ``"ChatRequest"``.
    :ivar category: категория лимита частоты, например ``"chat"``.
    :ivar body: поля запроса (без ``_type`` и ``rid``).
    """

    kind: str
    """Тип запроса, например ``"ChatRequest"`` или ``"ModerateRoomRequest"``."""
    category: str
    """Категория лимита частоты: ``chat``, ``move``, ``info`` и т. д."""
    body: Mapping[str, object]
    """Поля запроса, кроме ``_type`` и ``rid``."""


@dataclass(slots=True)
class RecordingRequester:
    """Замена соединения в тестах: записывает каждый запрос и отвечает по заготовкам.

    Подставляется в :class:`BotAPI` вместо настоящего движка. Поля задают то,
    что «знает сервер»: состав комнаты, золото, гардероб, права.

    :ivar sent: все отправленные запросы по порядку.
    :ivar room: состав комнаты, который вернёт ``list_room_users``.
    :ivar gold: золото в кошельке.
    :ivar inventory: гардероб бота.
    :ivar permissions: права, которые вернёт ``privileges``.
    :ivar tips_paid: оплачиваются ли чаевые и покупки.
    :ivar conversation_frames: кадры диалогов, которые вернёт ``conversations``.
    :ivar message_frames: кадры сообщений, которые вернёт ``messages``.
    :ivar refuse_with: если задано, любой запрос отклоняется с этим текстом.
    """

    sent: list[Sent] = field(default_factory=list[Sent])
    """Все отправленные запросы по порядку."""
    room: list[RoomUser] = field(default_factory=list[RoomUser])
    """Состав комнаты, который вернёт ``list_room_users``."""
    gold: int = 0
    """Золото в кошельке бота."""
    inventory: list[Item] = field(default_factory=list[Item])
    """Гардероб бота."""
    permissions: RoomPermissions = RoomPermissions(moderator=False, designer=False)
    """Права, которые вернёт ``privileges``."""
    # Оплачиваются ли чаевые; False отвечает ``insufficient_funds``, как сервер.
    tips_paid: bool = True
    """Оплачиваются ли чаевые и покупки; ``False`` — ответ ``insufficient_funds``, как у сервера."""
    # Кадры, которые прислал бы сервер на запросы личных сообщений.
    conversation_frames: list[protocol.Frame] = field(default_factory=list[protocol.Frame])
    """Кадры диалогов, которые вернёт ``conversations``."""
    message_frames: list[protocol.Frame] = field(default_factory=list[protocol.Frame])
    """Кадры сообщений, которые вернёт ``messages``."""
    # Если задано, любой запрос отклоняется этим текстом, как это сделал бы сервер.
    refuse_with: str | None = None
    """Если задано, любой запрос отклоняется :class:`ResponseError` с этим текстом."""

    async def request(self, type_name: str, category: str, body: Mapping[str, object]) -> protocol.Frame:
        """Записать запрос и ответить заготовкой.

        :raises ResponseError: если задано ``refuse_with``.
        """
        self.sent.append(Sent(type_name, category, dict(body)))
        if self.refuse_with is not None:
            raise ResponseError(self.refuse_with)
        return self._answer(type_name)

    def _answer(self, type_name: str) -> protocol.Frame:
        response = type_name.removesuffix("Request") + "Response"
        if type_name == "GetRoomUsersRequest":
            return {"_type": response, "content": [protocol.room_user_entry(entry) for entry in self.room]}
        if type_name == "GetWalletRequest":
            return {"_type": response, "content": [{"type": "gold", "amount": self.gold}]}
        if type_name == "GetInventoryRequest":
            return {"_type": response, "items": [protocol.item_body(item) for item in self.inventory]}
        if type_name == "GetRoomPrivilegeRequest":
            return {
                "_type": response,
                "content": {"moderator": self.permissions.moderator, "designer": self.permissions.designer},
            }
        if type_name == "GetUserOutfitRequest":
            return {"_type": response, "outfit": []}
        if type_name in ("TipUserRequest", "BuyItemRequest"):
            return {"_type": response, "result": "success" if self.tips_paid else "insufficient_funds"}
        if type_name == "GetConversationsRequest":
            return {"_type": response, "conversations": list(self.conversation_frames), "not_joined": 0}
        if type_name == "GetMessagesRequest":
            return {"_type": response, "messages": list(self.message_frames)}
        return {"_type": response}


class Harness[B: Bot]:
    """Запускает одного бота в памяти так, словно он подключён к комнате.

    События подаются прямо в бота и обрабатываются так же, как в настоящем
    подключении: сначала срабатывает ожидание ``wait_for``, затем обработчики и
    команды. Каждый вызов ``say``, ``join``, ``emit`` возвращается, когда бот
    закончил обработку события. Действия бота (``api.chat`` и др.) не уходят в
    сеть, а записываются в :attr:`requester`.

    Диалог через ``wait_for`` в тесте запускайте так: команду — отдельной
    задачей (``asyncio.create_task(harness.say(...))``), ответ подавайте
    следующим вызовом, затем дожидайтесь задачи.

    :ivar bot: бот под тестом.
    :ivar requester: записывающий «сервер» (:class:`RecordingRequester`).
    :ivar session: сессия, которую получил бот.
    """

    def __init__(
        self,
        bot: B,
        *,
        bot_id: str = "bot-1",
        owner_id: str = "owner-1",
        room_name: str = "Test room",
        clean_room: bool = False,
    ) -> None:
        """Подготовить стенд. Бот пока не запущен: вызовите :meth:`start`.

        :param bot: бот под тестом.
        :param bot_id: идентификатор аккаунта бота в тесте.
        :param owner_id: идентификатор владельца комнаты (для ``owner_only`` и ``is_owner``).
        :param room_name: название комнаты.
        :param clean_room: проверять режим «чистой комнаты».
        """
        self.bot = bot
        """Бот под тестом."""
        self.requester = RecordingRequester()
        """Записывающий «сервер»: здесь лежат отправленные запросы и заготовки ответов."""
        self.session = SessionMetadata(
            user_id=bot_id,
            room_info=RoomInfo(owner_id=owner_id, room_name=room_name),
            rate_limits={},
            connection_id="test-connection",
        )
        """Сессия, которую получает бот."""
        bot._attach(self.requester, self.session, clean_room)

    async def start(self) -> None:
        """Подключить бота: вызывается ``on_start`` и, если не «чистая комната», заполняется состав.

        Таймеры ``@every`` в тесте не запускаются; проверяйте такой метод,
        вызывая его напрямую.
        """
        await self.bot._on_session(self.session)

    async def emit(self, event: Event) -> None:
        """Доставить боту одно событие так, как это сделало бы соединение.

        :param event: любое событие SDK, например :class:`UserJoinedEvent`.
        """
        self.bot._on_arrival(event)
        await self.bot._on_event(event)

    async def say(self, username: str, message: str, *, whisper: bool = False) -> None:
        """Сделать так, чтобы пользователь написал в чат или прошептал боту.

        Идентификатор пользователя в тесте — ``"user-" + username``.

        :param username: имя пользователя.
        :param message: текст.
        :param whisper: ``True`` — шёпот боту, ``False`` — общий чат.
        """
        await self.emit(ChatEvent(User(id=f"user-{username}", username=username), message, whisper))

    async def join(self, username: str, position: Location = Position(0.0, 0.0, 0.0)) -> User:
        """Ввести пользователя в комнату: он попадает в состав комнаты и приходит событие входа.

        :param username: имя пользователя (идентификатор — ``"user-" + username``).
        :param position: где он появляется.
        :returns: созданный пользователь.
        """
        user = User(id=f"user-{username}", username=username)
        self.requester.room.append(RoomUser(user, position))
        await self.emit(UserJoinedEvent(user, position))
        return user

    @staticmethod
    def event_tip(sender: User, receiver: User, item: Item | CurrencyItem) -> TipEvent:
        """Собрать событие чаевых, готовое к ``emit``.

        :param sender: кто дал.
        :param receiver: кто получил.
        :param item: золото (:class:`CurrencyItem`) или предмет (:class:`Item`).
        """
        return TipEvent(sender=sender, receiver=receiver, item=item)

    async def leave(self, user: User) -> None:
        """Вывести пользователя из комнаты: убрать из состава и подать событие выхода.

        :param user: кого вывести.
        """
        self.requester.room = [entry for entry in self.requester.room if entry.user.id != user.id]
        await self.emit(UserLeftEvent(user))

    @property
    def chats(self) -> list[str]:
        """Все реплики бота в общий чат по порядку."""
        return [
            str(sent.body["message"])
            for sent in self.requester.sent
            if sent.kind == "ChatRequest" and sent.body.get("whisper_target_id") is None
        ]

    @property
    def whispers(self) -> list[str]:
        """Все шёпоты бота по порядку."""
        return [
            str(sent.body["message"])
            for sent in self.requester.sent
            if sent.kind == "ChatRequest" and sent.body.get("whisper_target_id") is not None
        ]

    def requests(self, kind: str) -> list[Sent]:
        """Получить все запросы одного вида, например ``"ModerateRoomRequest"``.

        :param kind: тип запроса.
        :returns: запросы этого типа по порядку.
        """
        return [sent for sent in self.requester.sent if sent.kind == kind]
