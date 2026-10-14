"""Неизменяемые данные, которые SDK передаёт коду бота.

Все классы здесь — «замороженные» dataclass'ы: после создания их нельзя
изменить, их безопасно хранить, сравнивать и использовать как ключи словаря.
Названия полей совпадают с официальным Python SDK Highrise, поэтому код,
написанный под тот SDK, читается так же.

Модели делятся на четыре группы:

* **люди и места** — :class:`User`, :class:`Position`, :class:`AnchorPosition`,
  :class:`RoomUser`, :class:`RoomInfo`, :class:`RoomPermissions`;
* **вещи и деньги** — :class:`Item`, :class:`CurrencyItem`;
* **события комнаты** — классы ``*Event``, объединённые в :data:`Event`;
* **личные сообщения и сессия** — :class:`DirectMessage`, :class:`Conversation`,
  :class:`ConversationPage`, :class:`SessionMetadata`, :class:`RateLimit`.

Единственное изменяемое состояние SDK — состав комнаты (:class:`sukarisebot.Room`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

Facing = Literal["FrontRight", "FrontLeft", "BackRight", "BackLeft"]
"""Куда смотрит персонаж: одно из четырёх изометрических направлений."""

FACINGS: frozenset[str] = frozenset(("FrontRight", "FrontLeft", "BackRight", "BackLeft"))
"""Все допустимые значения :data:`Facing` в виде множества, для проверок."""

Reaction = Literal["clap", "heart", "thumbs", "wave", "wink"]
"""Реакция, которую можно отправить пользователю: аплодисменты, сердце, палец вверх, приветствие, подмигивание."""

REACTIONS: frozenset[str] = frozenset(("clap", "heart", "thumbs", "wave", "wink"))
"""Все допустимые значения :data:`Reaction` в виде множества, для проверок."""

GoldBar = Literal[
    "gold_bar_1",
    "gold_bar_5",
    "gold_bar_10",
    "gold_bar_50",
    "gold_bar_100",
    "gold_bar_500",
    "gold_bar_1k",
    "gold_bar_5000",
    "gold_bar_10k",
]
"""Слиток золота для чаевых. Число в названии — сколько золота получает адресат.

``gold_bar_1k`` — тысяча, ``gold_bar_10k`` — десять тысяч. Отправитель платит
чуть больше, чем получает адресат (например, 11 золота за ``gold_bar_10``).
"""

GOLD_BARS: frozenset[str] = frozenset(
    (
        "gold_bar_1",
        "gold_bar_5",
        "gold_bar_10",
        "gold_bar_50",
        "gold_bar_100",
        "gold_bar_500",
        "gold_bar_1k",
        "gold_bar_5000",
        "gold_bar_10k",
    )
)
"""Все допустимые значения :data:`GoldBar` в виде множества, для проверок."""

ModerationAction = Literal["kick", "ban", "unban", "mute"]
"""Действие модерации: выгнать, заблокировать, разблокировать, заглушить."""

MODERATION_ACTIONS: frozenset[str] = frozenset(("kick", "ban", "unban", "mute"))
"""Все допустимые значения :data:`ModerationAction` в виде множества, для проверок."""


@dataclass(frozen=True, slots=True)
class User:
    """Пользователь SukaRise: игрок или другой бот.

    Приходит в обработчиках событий и в списке людей комнаты. Сравнивайте
    пользователей по ``id``: имя игрок может сменить.

    :ivar id: постоянный идентификатор аккаунта.
    :ivar username: имя в игре на момент события.
    """

    id: str
    """Постоянный идентификатор аккаунта; не меняется при смене имени."""
    username: str
    """Имя в игре на момент события."""


@dataclass(frozen=True, slots=True)
class Position:
    """Точка на полу комнаты и направление взгляда.

    Координаты задаются в единицах комнаты. ``x`` и ``z`` — позиция на полу,
    ``y`` — высота (для обычного пола ``0.0``). Допустимые значения —
    конечные числа в пределах ±1000.

    :ivar x: координата по оси X.
    :ivar y: высота над полом.
    :ivar z: координата по оси Z.
    :ivar facing: куда смотрит персонаж; по умолчанию ``"FrontRight"``.
    """

    x: float
    """Координата по оси X."""
    y: float
    """Высота над полом; для обычного пола ``0.0``."""
    z: float
    """Координата по оси Z."""
    facing: Facing = "FrontRight"
    """Направление взгляда: ``FrontRight``, ``FrontLeft``, ``BackRight`` или ``BackLeft``."""


@dataclass(frozen=True, slots=True)
class AnchorPosition:
    """Место для сидения на предмете мебели.

    Если игрок сидит, его положение в комнате — это :class:`AnchorPosition`,
    а не :class:`Position`. Чтобы посадить бота, передайте такое место в
    :meth:`BotAPI.sit_on`.

    :ivar entity_id: идентификатор предмета мебели в комнате.
    :ivar anchor_ix: номер места на этом предмете (от 0 до 255).
    """

    entity_id: str
    """Идентификатор предмета мебели в комнате."""
    anchor_ix: int
    """Номер места на предмете мебели, от 0 до 255."""


Location = Union[Position, AnchorPosition]
"""Где находится пользователь: точка на полу (:class:`Position`) или место на мебели (:class:`AnchorPosition`).

Различайте их через ``isinstance`` или ``match``::

    match location:
        case Position(x=x, z=z):
            ...
        case AnchorPosition(entity_id=furniture):
            ...
"""


@dataclass(frozen=True, slots=True)
class CurrencyItem:
    """Сумма в одной валюте: строка кошелька или чаевые золотом.

    :ivar type: название валюты; золото — ``"gold"``.
    :ivar amount: количество.
    """

    type: str
    """Название валюты; золото — ``"gold"``."""
    amount: int
    """Количество единиц валюты."""


@dataclass(frozen=True, slots=True)
class Item:
    """Предмет: часть одежды в гардеробе или наряде.

    :ivar type: вид предмета; для одежды ``"clothing"``.
    :ivar amount: количество (для одежды 1).
    :ivar id: идентификатор предмета в каталоге, например ``shirt-n_plaid_blackwhite``.
    :ivar account_bound: предмет привязан к аккаунту и не передаётся другим.
    :ivar active_palette: номер выбранной палитры цветов или ``None``.
    """

    type: str
    """Вид предмета; для одежды ``"clothing"``."""
    amount: int
    """Количество; для одежды 1."""
    id: str
    """Идентификатор предмета в каталоге, например ``shirt-n_plaid_blackwhite``."""
    account_bound: bool = False
    """Предмет привязан к аккаунту и не передаётся другим."""
    active_palette: int | None = None
    """Номер выбранной палитры цветов или ``None``, если палитра по умолчанию."""


@dataclass(frozen=True, slots=True)
class RoomUser:
    """Человек (или бот) в комнате и его положение.

    Элементы списка :meth:`BotAPI.list_room_users` и :meth:`Room.users`.

    :ivar user: кто это.
    :ivar location: где он находится: на полу или на мебели.
    """

    user: User
    """Кто это."""
    location: Location
    """Где он находится: точка на полу или место на мебели."""


@dataclass(frozen=True, slots=True)
class RoomPermissions:
    """Права пользователя в комнате. ``None`` означает «сервер не сообщил».

    :ivar moderator: может ли модерировать комнату.
    :ivar designer: может ли редактировать комнату.
    """

    moderator: bool | None = None
    """Может ли пользователь модерировать комнату; ``None`` — сервер не сообщил."""
    designer: bool | None = None
    """Может ли пользователь редактировать комнату; ``None`` — сервер не сообщил."""


@dataclass(frozen=True, slots=True)
class RoomInfo:
    """Сведения о комнате, в которой работает бот.

    :ivar owner_id: идентификатор владельца комнаты.
    :ivar room_name: название комнаты.
    """

    owner_id: str
    """Идентификатор владельца комнаты."""
    room_name: str
    """Название комнаты."""


@dataclass(frozen=True, slots=True)
class RateLimit:
    """Лимит частоты для одной категории запросов: не больше ``requests`` за ``seconds`` секунд.

    :ivar requests: сколько запросов разрешено.
    :ivar seconds: за какое окно времени, в секундах.
    """

    requests: int
    """Сколько запросов разрешено за окно."""
    seconds: float
    """Длина окна в секундах."""


@dataclass(frozen=True, slots=True)
class SessionMetadata:
    """Первый кадр принятого подключения: кто бот, где он и какие у него лимиты.

    Приходит в :meth:`Bot.on_start` и доступен как ``bot.session``.

    :ivar user_id: идентификатор аккаунта самого бота.
    :ivar room_info: комната, в которую бот вошёл.
    :ivar rate_limits: лимиты частоты по категориям (``chat``, ``move``, ``info`` и т. д.).
    :ivar connection_id: идентификатор этого подключения (для журналов и отладки).
    """

    user_id: str
    """Идентификатор аккаунта самого бота."""
    room_info: RoomInfo
    """Комната, в которую бот вошёл."""
    rate_limits: dict[str, RateLimit]
    """Лимиты частоты по категориям: ``chat``, ``move``, ``info`` и другим."""
    connection_id: str
    """Идентификатор этого подключения; полезен в журналах и при обращении в поддержку."""


@dataclass(frozen=True, slots=True)
class ChatEvent:
    """Реплика в чате: публичная или шёпот, адресованный боту.

    Приходит в :meth:`Bot.on_chat` (``whisper=False``) и :meth:`Bot.on_whisper`
    (``whisper=True``).

    :ivar user: кто написал.
    :ivar message: текст реплики.
    :ivar whisper: ``True`` — личное сообщение боту, ``False`` — общий чат.
    """

    user: User
    """Кто написал."""
    message: str
    """Текст реплики."""
    whisper: bool
    """``True`` — шёпот боту, ``False`` — реплика в общий чат."""


@dataclass(frozen=True, slots=True)
class EmoteEvent:
    """Эмоция, сыгранная пользователем.

    :ivar user: кто сыграл эмоцию.
    :ivar emote_id: идентификатор эмоции.
    :ivar receiver: кому она адресована или ``None``, если никому.
    """

    user: User
    """Кто сыграл эмоцию."""
    emote_id: str
    """Идентификатор эмоции, например ``emote-wave``."""
    receiver: User | None
    """Кому адресована эмоция; ``None``, если она ни на кого не направлена."""


@dataclass(frozen=True, slots=True)
class ReactionEvent:
    """Реакция, которую один пользователь отправил другому.

    :ivar user: кто отправил.
    :ivar reaction: название реакции (``clap``, ``heart``, ``thumbs``, ``wave``, ``wink``).
    :ivar receiver: кому адресована.
    """

    user: User
    """Кто отправил реакцию."""
    reaction: str
    """Название реакции: ``clap``, ``heart``, ``thumbs``, ``wave`` или ``wink``."""
    receiver: User
    """Кому адресована реакция."""


@dataclass(frozen=True, slots=True)
class UserJoinedEvent:
    """Пользователь вошёл в комнату.

    :ivar user: кто вошёл.
    :ivar position: где он появился.
    """

    user: User
    """Кто вошёл."""
    position: Location
    """Где он появился."""


@dataclass(frozen=True, slots=True)
class UserLeftEvent:
    """Пользователь вышел из комнаты.

    :ivar user: кто вышел.
    """

    user: User
    """Кто вышел."""


@dataclass(frozen=True, slots=True)
class UserMovedEvent:
    """Пользователь пошёл в другую точку или сел на мебель.

    :ivar user: кто переместился.
    :ivar position: куда: точка на полу или место на мебели.
    """

    user: User
    """Кто переместился."""
    position: Location
    """Куда он пошёл или где сел."""


@dataclass(frozen=True, slots=True)
class ChannelEvent:
    """Скрытое сообщение от другого бота в той же комнате.

    Игроки такие сообщения не видят: это канал связи между ботами
    (см. :meth:`BotAPI.channel`).

    :ivar sender_id: идентификатор бота-отправителя.
    :ivar message: текст сообщения.
    :ivar tags: метки, которыми отправитель пометил сообщение.
    """

    sender_id: str
    """Идентификатор бота-отправителя."""
    message: str
    """Текст сообщения."""
    tags: tuple[str, ...]
    """Метки, которыми отправитель пометил сообщение."""


@dataclass(frozen=True, slots=True)
class TipEvent:
    """Чаевые, отправленные в комнате: золото или предмет.

    Событие приходит о любых чаевых в комнате, а не только о чаевых боту. Чтобы
    отличить чаевые боту, сравните ``receiver.id`` с ``bot.session.user_id``.

    :ivar sender: кто дал чаевые.
    :ivar receiver: кто их получил.
    :ivar item: что отдано: :class:`CurrencyItem` для золота, :class:`Item` для предмета.
    """

    sender: User
    """Кто дал чаевые."""
    receiver: User
    """Кто получил чаевые."""
    item: Item | CurrencyItem
    """Что отдано: :class:`CurrencyItem` для золота, :class:`Item` для предмета."""


@dataclass(frozen=True, slots=True)
class MessageEvent:
    """Боту пришло личное сообщение.

    Само сообщение в событии не приходит: прочитайте его через
    :meth:`BotAPI.messages`, ответьте через :meth:`BotAPI.send_message`.

    :ivar user_id: идентификатор написавшего.
    :ivar conversation_id: диалог, в который пришло сообщение.
    :ivar is_new_conversation: ``True``, если это первое сообщение диалога.
    """

    user_id: str
    """Идентификатор написавшего пользователя."""
    conversation_id: str
    """Диалог, в который пришло сообщение."""
    is_new_conversation: bool
    """``True``, если это первое сообщение диалога."""


@dataclass(frozen=True, slots=True)
class DirectMessage:
    """Одно сообщение личного диалога.

    :ivar message_id: идентификатор сообщения.
    :ivar conversation_id: диалог, к которому оно относится.
    :ivar created_at: время отправки, как его прислал сервер, или ``None``.
    :ivar content: текст сообщения.
    :ivar sender_id: идентификатор отправителя.
    :ivar category: вид сообщения: ``text`` или ``invite`` (приглашение).
    """

    message_id: str
    """Идентификатор сообщения; годится для постраничного чтения назад."""
    conversation_id: str
    """Диалог, к которому относится сообщение."""
    created_at: str | None
    """Время отправки в том виде, в каком его прислал сервер, или ``None``."""
    content: str
    """Текст сообщения."""
    sender_id: str
    """Идентификатор отправителя."""
    category: str
    """Вид сообщения: ``text`` (обычный текст) или ``invite`` (приглашение)."""


@dataclass(frozen=True, slots=True)
class Conversation:
    """Личный диалог, в котором участвует бот. Боты участвуют только в личных диалогах.

    :ivar id: идентификатор диалога.
    :ivar did_join: принял ли бот диалог (запросы принимаются за бота сразу).
    :ivar unread_count: сколько сообщений бот ещё не прочитал.
    :ivar last_message: последнее сообщение или ``None``.
    :ivar muted: отключены ли уведомления диалога.
    :ivar member_ids: идентификаторы участников.
    :ivar owner_id: создатель диалога или ``None``.
    """

    id: str
    """Идентификатор диалога."""
    did_join: bool
    """Принял ли бот диалог; запросы принимаются за бота сразу."""
    unread_count: int
    """Сколько сообщений бот ещё не прочитал."""
    last_message: DirectMessage | None
    """Последнее сообщение диалога или ``None``."""
    muted: bool
    """Отключены ли уведомления диалога."""
    member_ids: tuple[str, ...]
    """Идентификаторы участников диалога."""
    owner_id: str | None
    """Создатель диалога или ``None``."""


@dataclass(frozen=True, slots=True)
class ConversationPage:
    """Страница диалогов бота: до 20 штук.

    :ivar conversations: диалоги страницы.
    :ivar not_joined: сколько запросов на диалог бот ещё не принял.
    """

    conversations: tuple[Conversation, ...]
    """Диалоги этой страницы, не больше 20."""
    not_joined: int
    """Сколько запросов на диалог бот ещё не принял; обычно 0."""


@dataclass(frozen=True, slots=True)
class ModerationEvent:
    """В комнате выполнено действие модерации.

    Бот не получает событие о действии, которое выполнил сам.

    :ivar moderator_id: кто выполнил действие.
    :ivar target_user_id: к кому оно применено.
    :ivar moderation_type: что сделано: ``kick``, ``ban``, ``unban`` или ``mute``.
    :ivar duration: длительность в секундах или ``None``, если срок не задан.
    """

    moderator_id: str
    """Кто выполнил действие."""
    target_user_id: str
    """К кому действие применено."""
    moderation_type: str
    """Что сделано: ``kick``, ``ban``, ``unban`` или ``mute``."""
    duration: int | None
    """Длительность в секундах или ``None``, если срок не задан."""


Event = Union[
    ChatEvent,
    EmoteEvent,
    ReactionEvent,
    UserJoinedEvent,
    UserLeftEvent,
    UserMovedEvent,
    ChannelEvent,
    ModerationEvent,
    TipEvent,
    MessageEvent,
]
"""Любое событие, которое SDK доставляет боту.

Используется в подсказках типов (``wait_for``, ``on_error``) и удобен для
``match``-разбора::

    match event:
        case ChatEvent(user=user, message=text):
            ...
        case UserJoinedEvent(user=user):
            ...
"""
