"""Frames must read and write exactly what internal/botapi/wire.go defines."""

from __future__ import annotations

import json

import pytest

from sukarisebot import (
    AnchorPosition,
    ChannelEvent,
    ChatEvent,
    CurrencyItem,
    EmoteEvent,
    Item,
    ModerationEvent,
    Position,
    RateLimit,
    RoomPermissions,
    RoomUser,
    User,
    UserJoinedEvent,
)
from sukarisebot.errors import ProtocolError
from sukarisebot.protocol import (
    currencies,
    decode,
    encode,
    item_body,
    parse_event,
    parse_location,
    parse_session,
    permissions,
    room_users,
)


def test_request_frames_use_the_server_field_names() -> None:
    frame = json.loads(encode("ChatRequest", "7", {"message": "hi", "whisper_target_id": None}))
    assert frame == {"_type": "ChatRequest", "rid": "7", "message": "hi", "whisper_target_id": None}


def test_keepalive_carries_no_rid() -> None:
    assert json.loads(encode("KeepaliveRequest", None, {})) == {"_type": "KeepaliveRequest"}


def test_chat_events_parse_into_typed_values() -> None:
    frame = decode(json.dumps({"_type": "ChatEvent", "user": {"id": "u1", "username": "alice"}, "message": "hi", "whisper": True}))
    assert parse_event(frame) == ChatEvent(User("u1", "alice"), "hi", True)


def test_channel_and_moderation_events_parse() -> None:
    channel = decode('{"_type":"ChannelEvent","sender_id":"bot-2","msg":"ping","tags":["a","b"]}')
    assert parse_event(channel) == ChannelEvent("bot-2", "ping", ("a", "b"))
    moderated = decode('{"_type":"RoomModeratedEvent","moderatorId":"o","targetUserId":"t","moderationType":"kick","duration":null}')
    assert parse_event(moderated) == ModerationEvent("o", "t", "kick", None)


def test_emote_with_and_without_receiver() -> None:
    solo = decode('{"_type":"EmoteEvent","user":{"id":"u1","username":"a"},"emote_id":"wave","receiver":null}')
    assert parse_event(solo) == EmoteEvent(User("u1", "a"), "wave", None)


def test_unknown_event_kinds_are_skipped_not_fatal() -> None:
    assert parse_event(decode('{"_type":"VoiceEvent"}')) is None


def test_a_join_event_carries_its_location() -> None:
    frame = decode('{"_type":"UserJoinedEvent","user":{"id":"u1","username":"a"},"position":{"entity_id":"e9","anchor_ix":1}}')
    assert parse_event(frame) == UserJoinedEvent(User("u1", "a"), AnchorPosition("e9", 1))


def test_locations_tell_positions_from_seats() -> None:
    assert parse_location({"entity_id": "e1", "anchor_ix": 2}) == AnchorPosition("e1", 2)
    assert parse_location({"x": 1, "y": 0, "z": 2, "facing": "BackLeft"}) == Position(1.0, 0.0, 2.0, "BackLeft")


def test_a_missing_facing_defaults_to_front_right() -> None:
    assert parse_location({"x": 0, "y": 0, "z": 0}) == Position(0.0, 0.0, 0.0, "FrontRight")


def test_an_unknown_facing_is_a_protocol_error() -> None:
    with pytest.raises(ProtocolError, match="facing"):
        parse_location({"x": 0, "y": 0, "z": 0, "facing": "Up"})


def test_session_metadata_reads_rate_limits() -> None:
    session = parse_session(
        {
            "_type": "SessionMetadata",
            "user_id": "bot-1",
            "room_info": {"owner_id": "owner-1", "room_name": "Lobby"},
            "rate_limits": {"chat": [20, 10]},
            "connection_id": "c-1",
            "sdk_version": None,
        }
    )
    assert session.user_id == "bot-1"
    assert session.room_info.owner_id == "owner-1"
    assert session.rate_limits == {"chat": RateLimit(20, 10.0)}


def test_room_users_are_user_location_pairs() -> None:
    frame = {"_type": "GetRoomUsersResponse", "content": [[{"id": "u1", "username": "alice"}, {"x": 1, "y": 0, "z": 2, "facing": "FrontLeft"}]]}
    (entry,) = room_users(frame)
    assert entry == RoomUser(User("u1", "alice"), Position(1.0, 0.0, 2.0, "FrontLeft"))


def test_wallet_and_permissions_responses() -> None:
    assert currencies({"_type": "GetWalletResponse", "content": [{"type": "gold", "amount": 9}]}) == [CurrencyItem("gold", 9)]
    assert permissions({"_type": "GetRoomPrivilegeResponse", "content": {"moderator": True, "designer": None}}) == RoomPermissions(True, None)


def test_items_round_trip_through_their_body() -> None:
    item = Item(type="clothing", amount=1, id="shirt-1", account_bound=True, active_palette=2)
    assert item_body(item) == {"type": "clothing", "amount": 1, "id": "shirt-1", "account_bound": True, "active_palette": 2}


@pytest.mark.parametrize("text", ["not json", "[1, 2]", '{"x": 1}'])
def test_malformed_frames_are_protocol_errors(text: str) -> None:
    with pytest.raises(ProtocolError):
        decode(text)


def test_tips_carry_gold_or_an_item() -> None:
    from sukarisebot import TipEvent

    gold = decode('{"_type":"TipReactionEvent","sender":{"id":"u1","username":"a"},"receiver":{"id":"bot-1","username":"bot"},"item":{"type":"gold","amount":50}}')
    assert parse_event(gold) == TipEvent(User("u1", "a"), User("bot-1", "bot"), CurrencyItem("gold", 50))
    item = decode('{"_type":"TipReactionEvent","sender":{"id":"u1","username":"a"},"receiver":{"id":"bot-1","username":"bot"},"item":{"type":"clothing","amount":1,"id":"hat-3","account_bound":false,"active_palette":null}}')
    tip = parse_event(item)
    assert isinstance(tip, TipEvent) and tip.item == Item(type="clothing", amount=1, id="hat-3", account_bound=False, active_palette=None)
