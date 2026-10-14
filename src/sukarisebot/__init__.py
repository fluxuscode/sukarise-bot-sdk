"""SukaRiseBot: типизированный asyncio SDK для ботов SukaRise.

Бот — это аккаунт SukaRise, которым управляет программа через один websocket.
Наследуйте :class:`Bot`, переопределите нужные обработчики и запустите::

    from sukarisebot import Bot, Location, User

    class Greeter(Bot):
        async def on_user_join(self, user: User, position: Location) -> None:
            await self.api.chat(f"Добро пожаловать, {user.username}!")

    Greeter().start(token="srbot_...", room_id="room-...")

Что где лежит:

* :class:`Bot` — база для вашего бота: обработчики ``on_...``, команды, таймеры;
* :class:`BotAPI` — действия бота (``bot.api``): чат, движение, модерация, чаевые, сообщения;
* модели данных — :class:`User`, :class:`Position`, :class:`Item` и классы событий ``*Event``;
* исключения — :class:`SukaRiseError` и его потомки;
* :class:`JsonStore` — хранилище данных между запусками;
* :class:`Harness` — тестирование бота без сервера.

Полная документация — в каталоге ``docs/`` репозитория.
"""

from .api import BotAPI, split_message
from .bot import ENV_ROOM_ID, ENV_TOKEN, ENV_URL, Bot
from .cli import load_bot
from .commands import Command, CommandHandler, Commands, Context, Phrases
from .decorators import CommandSpec, command, every
from .engine import DEFAULT_URL, Engine, Requester
from .errors import (
    ConnectionRefused,
    InvalidArgument,
    NotConnected,
    ProtocolError,
    RequestTimeout,
    ResponseError,
    SukaRiseError,
)
from .models import (
    FACINGS,
    GOLD_BARS,
    MODERATION_ACTIONS,
    REACTIONS,
    AnchorPosition,
    ChannelEvent,
    ChatEvent,
    Conversation,
    ConversationPage,
    CurrencyItem,
    DirectMessage,
    EmoteEvent,
    Event,
    Facing,
    GoldBar,
    Item,
    Location,
    MessageEvent,
    ModerationAction,
    ModerationEvent,
    Position,
    RateLimit,
    Reaction,
    ReactionEvent,
    RoomInfo,
    RoomPermissions,
    RoomUser,
    SessionMetadata,
    TipEvent,
    User,
    UserJoinedEvent,
    UserLeftEvent,
    UserMovedEvent,
)
from .outfit import category_of, outfit_problems
from .room import Room
from .storage import JsonStore, JsonValue
from .testing import Harness, RecordingRequester, Sent

__version__ = "0.1.0"
"""Версия SDK."""

__all__ = [
    "DEFAULT_URL",
    "ENV_ROOM_ID",
    "ENV_TOKEN",
    "ENV_URL",
    "FACINGS",
    "GOLD_BARS",
    "MODERATION_ACTIONS",
    "REACTIONS",
    "AnchorPosition",
    "Bot",
    "BotAPI",
    "ChannelEvent",
    "ChatEvent",
    "Command",
    "CommandHandler",
    "CommandSpec",
    "Commands",
    "ConnectionRefused",
    "Context",
    "Conversation",
    "ConversationPage",
    "CurrencyItem",
    "DirectMessage",
    "EmoteEvent",
    "Engine",
    "Event",
    "Facing",
    "GoldBar",
    "Harness",
    "InvalidArgument",
    "Item",
    "JsonStore",
    "JsonValue",
    "Location",
    "MessageEvent",
    "ModerationAction",
    "ModerationEvent",
    "NotConnected",
    "Phrases",
    "Position",
    "ProtocolError",
    "RateLimit",
    "Reaction",
    "ReactionEvent",
    "RecordingRequester",
    "Requester",
    "RequestTimeout",
    "ResponseError",
    "Room",
    "RoomInfo",
    "RoomPermissions",
    "RoomUser",
    "Sent",
    "SessionMetadata",
    "SukaRiseError",
    "TipEvent",
    "User",
    "UserJoinedEvent",
    "UserLeftEvent",
    "UserMovedEvent",
    "category_of",
    "command",
    "every",
    "load_bot",
    "outfit_problems",
    "split_message",
]
