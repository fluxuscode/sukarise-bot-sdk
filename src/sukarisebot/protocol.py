"""Кадры протокола ботов: кодирование, декодирование и типизированные разборщики.

Низкоуровневая часть SDK; обычному боту она не нужна. Протокол совместим с
официальным SDK Highrise: кадр — это JSON-объект с полем ``_type``. Запрос несёт
``rid`` — номер, который сервер возвращает в ответе; так ответ находит ждущий его
вызов. События (кадры без ``rid``) приходят от сервера сами.

Подробное описание протокола — в ``docs/protocol.md``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import cast

from .errors import ProtocolError
from .models import (
    FACINGS,
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
    Item,
    Location,
    MessageEvent,
    ModerationEvent,
    Position,
    RateLimit,
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

type Frame = dict[str, object]
"""Один кадр протокола: JSON-объект, уже разобранный в словарь."""


# ---- кодирование ----------------------------------------------------------------


def encode(type_name: str, rid: str | None, body: Mapping[str, object]) -> str:
    """Собрать JSON-строку запроса.

    :param type_name: тип запроса, попадает в поле ``_type``.
    :param rid: номер запроса; ``None`` для keepalive (он ответа не ждёт).
    :param body: остальные поля запроса.
    :returns: компактный JSON (без пробелов, кириллица не экранируется).
    """
    frame: dict[str, object] = {"_type": type_name}
    if rid is not None:
        frame["rid"] = rid
    frame.update(body)
    return json.dumps(frame, ensure_ascii=False, separators=(",", ":"))


def decode(text: str) -> Frame:
    """Разобрать кадр сервера.

    :param text: JSON-строка из сокета.
    :returns: кадр-словарь.
    :raises ProtocolError: это не JSON или не объект с полем ``_type``.
    """
    try:
        value = cast(object, json.loads(text))
    except ValueError as exc:
        raise ProtocolError("кадр — не JSON") from exc
    frame = cast(Frame, value) if isinstance(value, dict) else {}
    if not isinstance(frame.get("_type"), str):
        raise ProtocolError("в кадре нет поля _type")
    return frame


def frame_type(frame: Frame) -> str:
    """Получить тип кадра (значение поля ``_type``)."""
    return cast(str, frame["_type"])


# ---- доступ к полям ---------------------------------------------------------------


def _get(data: Mapping[str, object], key: str) -> object:
    if key not in data:
        raise ProtocolError(f"в кадре нет поля {key!r}")
    return data[key]


def _text_value(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise ProtocolError(f"{what} — не строка")
    return value


def _int_value(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError(f"{what} — не целое число")
    return value


def _real_value(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProtocolError(f"{what} — не число")
    return float(value)


def _object(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ProtocolError(f"{what} — не объект")
    return cast(Mapping[str, object], value)


def _array(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise ProtocolError(f"{what} — не массив")
    return cast(list[object], value)


def _text(data: Mapping[str, object], key: str) -> str:
    return _text_value(_get(data, key), key)


def _int(data: Mapping[str, object], key: str) -> int:
    return _int_value(_get(data, key), key)


def _bool(data: Mapping[str, object], key: str) -> bool:
    value = _get(data, key)
    if not isinstance(value, bool):
        raise ProtocolError(f"{key!r} — не логическое значение")
    return value


def _optional_int(data: Mapping[str, object], key: str) -> int | None:
    value = data.get(key)
    return None if value is None else _int_value(value, key)


def _optional_text(data: Mapping[str, object], key: str) -> str | None:
    value = data.get(key)
    return None if value is None else _text_value(value, key)


def _optional_bool(data: Mapping[str, object], key: str) -> bool | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ProtocolError(f"{key!r} — не логическое значение")
    return value


# ---- значения -----------------------------------------------------------------------


def parse_facing(value: object) -> Facing:
    """Разобрать направление взгляда.

    :raises ProtocolError: значение не из ``FrontRight``, ``FrontLeft``, ``BackRight``, ``BackLeft``.
    """
    if not isinstance(value, str) or value not in FACINGS:
        raise ProtocolError(f"неизвестное значение facing {value!r}")
    return cast(Facing, value)


def parse_user(value: object) -> User:
    """Разобрать пользователя из ``{"id": ..., "username": ...}``."""
    data = _object(value, "user")
    return User(id=_text(data, "id"), username=_text(data, "username"))


def parse_location(value: object) -> Location:
    """Разобрать положение: место на мебели (есть ``entity_id``) или точка на полу."""
    data = _object(value, "location")
    if "entity_id" in data:
        return AnchorPosition(entity_id=_text(data, "entity_id"), anchor_ix=_int(data, "anchor_ix"))
    return Position(
        x=_real_value(_get(data, "x"), "x"),
        y=_real_value(_get(data, "y"), "y"),
        z=_real_value(_get(data, "z"), "z"),
        facing=parse_facing(data.get("facing", "FrontRight")),
    )


def parse_item(value: object) -> Item:
    """Разобрать предмет."""
    data = _object(value, "item")
    return Item(
        type=_text(data, "type"),
        amount=_int(data, "amount"),
        id=_text(data, "id"),
        account_bound=data.get("account_bound") is True,
        active_palette=_optional_int(data, "active_palette"),
    )


def parse_session(frame: Frame) -> SessionMetadata:
    """Разобрать первый кадр подключения (``SessionMetadata``).

    :raises ProtocolError: в кадре нет нужных полей или они неверного типа.
    """
    room = _object(_get(frame, "room_info"), "room_info")
    limits: dict[str, RateLimit] = {}
    for name, pair in _object(_get(frame, "rate_limits"), "rate_limits").items():
        values = _array(pair, f"лимит {name}")
        if len(values) != 2:
            raise ProtocolError(f"лимит {name} — не пара")
        limits[name] = RateLimit(
            requests=_int_value(values[0], f"{name}: число запросов"),
            seconds=_real_value(values[1], f"{name}: секунды"),
        )
    return SessionMetadata(
        user_id=_text(frame, "user_id"),
        room_info=RoomInfo(owner_id=_text(room, "owner_id"), room_name=_text(room, "room_name")),
        rate_limits=limits,
        connection_id=_text(frame, "connection_id"),
    )


# ---- события --------------------------------------------------------------------------


def _chat(frame: Frame) -> Event:
    return ChatEvent(parse_user(_get(frame, "user")), _text(frame, "message"), _bool(frame, "whisper"))


def _emote(frame: Frame) -> Event:
    receiver = frame.get("receiver")
    return EmoteEvent(
        user=parse_user(_get(frame, "user")),
        emote_id=_text(frame, "emote_id"),
        receiver=None if receiver is None else parse_user(receiver),
    )


def _reaction(frame: Frame) -> Event:
    return ReactionEvent(
        user=parse_user(_get(frame, "user")),
        reaction=_text(frame, "reaction"),
        receiver=parse_user(_get(frame, "receiver")),
    )


def _joined(frame: Frame) -> Event:
    return UserJoinedEvent(parse_user(_get(frame, "user")), parse_location(_get(frame, "position")))


def _left(frame: Frame) -> Event:
    return UserLeftEvent(parse_user(_get(frame, "user")))


def _moved(frame: Frame) -> Event:
    return UserMovedEvent(parse_user(_get(frame, "user")), parse_location(_get(frame, "position")))


def _channel(frame: Frame) -> Event:
    tags = tuple(_text_value(tag, "tag") for tag in _array(_get(frame, "tags"), "tags"))
    return ChannelEvent(sender_id=_text(frame, "sender_id"), message=_text(frame, "msg"), tags=tags)


def _moderated(frame: Frame) -> Event:
    return ModerationEvent(
        moderator_id=_text(frame, "moderatorId"),
        target_user_id=_text(frame, "targetUserId"),
        moderation_type=_text(frame, "moderationType"),
        duration=_optional_int(frame, "duration"),
    )


def _tip(frame: Frame) -> Event:
    value = _object(_get(frame, "item"), "item")
    item: Item | CurrencyItem
    if "id" in value:
        item = parse_item(value)
    else:
        item = CurrencyItem(type=_text(value, "type"), amount=_int(value, "amount"))
    return TipEvent(sender=parse_user(_get(frame, "sender")), receiver=parse_user(_get(frame, "receiver")), item=item)


def _message(frame: Frame) -> Event:
    return MessageEvent(
        user_id=_text(frame, "user_id"),
        conversation_id=_text(frame, "conversation_id"),
        is_new_conversation=_bool(frame, "is_new_conversation"),
    )


_EVENT_PARSERS: dict[str, Callable[[Frame], Event]] = {
    "ChatEvent": _chat,
    "EmoteEvent": _emote,
    "ReactionEvent": _reaction,
    "UserJoinedEvent": _joined,
    "UserLeftEvent": _left,
    "UserMovedEvent": _moved,
    "ChannelEvent": _channel,
    "RoomModeratedEvent": _moderated,
    "TipReactionEvent": _tip,
    "MessageEvent": _message,
}


def parse_event(frame: Frame) -> Event | None:
    """Получить типизированное событие по кадру.

    :param frame: кадр сервера.
    :returns: событие или ``None``, если SDK такой вид кадров не моделирует.
    :raises ProtocolError: кадр известного вида, но поля неверны.
    """
    parser = _EVENT_PARSERS.get(frame_type(frame))
    return None if parser is None else parser(frame)


# ---- ответы -------------------------------------------------------------------------------


def room_users(frame: Frame) -> list[RoomUser]:
    """Разобрать ответ ``GetRoomUsersResponse``: пары «пользователь, положение»."""
    result: list[RoomUser] = []
    for entry in _array(_get(frame, "content"), "content"):
        pair = _array(entry, "room user")
        if len(pair) != 2:
            raise ProtocolError("запись о человеке в комнате — не пара")
        result.append(RoomUser(user=parse_user(pair[0]), location=parse_location(pair[1])))
    return result


def currencies(frame: Frame) -> list[CurrencyItem]:
    """Разобрать ответ ``GetWalletResponse``: валюты кошелька."""
    result: list[CurrencyItem] = []
    for entry in _array(_get(frame, "content"), "content"):
        data = _object(entry, "currency")
        result.append(CurrencyItem(type=_text(data, "type"), amount=_int(data, "amount")))
    return result


def paid(frame: Frame) -> bool:
    """Разобрать ответ на чаевые или покупку.

    :returns: ``True`` — оплачено (``success``), ``False`` — не хватило золота (``insufficient_funds``).
    :raises ProtocolError: сервер прислал другой результат.
    """
    result = _text(frame, "result")
    if result == "success":
        return True
    if result == "insufficient_funds":
        return False
    raise ProtocolError(f"неизвестный результат оплаты {result!r}")


def parse_direct_message(value: object) -> DirectMessage:
    """Разобрать одно личное сообщение."""
    data = _object(value, "message")
    return DirectMessage(
        message_id=_text(data, "message_id"),
        conversation_id=_text(data, "conversation_id"),
        created_at=_optional_text(data, "createdAt"),
        content=_text(data, "content"),
        sender_id=_text(data, "sender_id"),
        category=_text(data, "category"),
    )


def parse_conversation(value: object) -> Conversation:
    """Разобрать один личный диалог."""
    data = _object(value, "conversation")
    last = data.get("last_message")
    members = data.get("member_ids")
    return Conversation(
        id=_text(data, "id"),
        did_join=_bool(data, "did_join"),
        unread_count=_int(data, "unread_count"),
        last_message=None if last is None else parse_direct_message(last),
        muted=_bool(data, "muted"),
        member_ids=() if members is None else tuple(_text_value(member, "member id") for member in _array(members, "member_ids")),
        owner_id=_optional_text(data, "owner_id"),
    )


def conversations(frame: Frame) -> ConversationPage:
    """Разобрать ответ ``GetConversationsResponse``."""
    return ConversationPage(
        conversations=tuple(parse_conversation(entry) for entry in _array(_get(frame, "conversations"), "conversations")),
        not_joined=_int(frame, "not_joined"),
    )


def messages(frame: Frame) -> list[DirectMessage]:
    """Разобрать ответ ``GetMessagesResponse``: сообщения диалога."""
    return [parse_direct_message(entry) for entry in _array(_get(frame, "messages"), "messages")]


def permissions(frame: Frame) -> RoomPermissions:
    """Разобрать ответ ``GetRoomPrivilegeResponse``: права в комнате."""
    content = _object(_get(frame, "content"), "content")
    return RoomPermissions(
        moderator=_optional_bool(content, "moderator"),
        designer=_optional_bool(content, "designer"),
    )


def outfit(frame: Frame) -> list[Item]:
    """Разобрать ответ ``GetUserOutfitResponse``: надетые предметы."""
    return [parse_item(entry) for entry in _array(_get(frame, "outfit"), "outfit")]


def inventory(frame: Frame) -> list[Item]:
    """Разобрать ответ ``GetInventoryResponse``: гардероб."""
    return [parse_item(entry) for entry in _array(_get(frame, "items"), "items")]


def error_text(frame: Frame) -> str:
    """Получить текст отказа из кадра ``Error``; если текста нет, общую фразу."""
    message = frame.get("message")
    return message if isinstance(message, str) else "сервер сообщил об ошибке"


def wants_no_reconnect(frame: Frame) -> bool:
    """Узнать, просит ли кадр ``Error`` не подключаться заново (``do_not_reconnect``)."""
    return frame.get("do_not_reconnect") is True


# ---- тела запросов ---------------------------------------------------------------------------


def position_body(position: Position) -> dict[str, object]:
    """Собрать тело ``Position`` для запроса."""
    return {"x": position.x, "y": position.y, "z": position.z, "facing": position.facing}


def location_body(location: Location) -> dict[str, object]:
    """Собрать тело положения: место на мебели или точка на полу."""
    if isinstance(location, AnchorPosition):
        return {"entity_id": location.entity_id, "anchor_ix": location.anchor_ix}
    return position_body(location)


def item_body(item: Item) -> dict[str, object]:
    """Собрать тело предмета."""
    return {
        "type": item.type,
        "amount": item.amount,
        "id": item.id,
        "account_bound": item.account_bound,
        "active_palette": item.active_palette,
    }


def user_body(user: User) -> dict[str, object]:
    """Собрать тело пользователя."""
    return {"id": user.id, "username": user.username}


def room_user_entry(entry: RoomUser) -> list[object]:
    """Собрать запись «пользователь, положение» (используется тестовым стендом)."""
    return [user_body(entry.user), location_body(entry.location)]
