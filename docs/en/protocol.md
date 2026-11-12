**English** | [Русский](../ru/protocol.md) | [Português (Brasil)](../pt-BR/protocol.md)

# Protocol

This page describes exactly what the SDK sends over the network. You need it to understand how a
bot's requests are built, to debug the connection or to write a client in another language. For
ordinary work with the SDK you do not have to read it.

The protocol is compatible with the official Highrise Python SDK: frames are tagged with the
`_type` field and requests are numbered with the `rid` field. Code and bots written for that
protocol work with the same format; only the address differs.

## Connecting

The bot opens a **websocket** at the gateway's address (by default
`wss://production-portal-refb.sukarise.ru/web/botapi`, overridden by the `url` argument or the
`SUKARISEBOT_URL` variable). The method is `GET` with an upgrade to websocket.

| What | Where | Value |
|---|---|---|
| The bot's token | the `api-token` header | `srbot_…` from the personal cabinet |
| The room | the `room-id` header | the room's identifier, at most 128 bytes |
| Subscriptions | the `events` address parameter | for example `?events=chat,user_joined` |

The allowed subscription names: `chat`, `emote`, `reaction`, `user_joined`, `user_left`,
`user_moved`, `channel`, `moderation`, `tip_reaction`, `message`, `voice`. The SDK picks them from
the overridden handlers (see [How the SDK works](architecture.md#event-subscriptions)). If no
subscriptions are given, the server sends all the events.

If the connection is refused, the server sends an `Error` frame (see below) or answers with an
HTTP error before the upgrade to websocket.

## Frames

Each frame is a JSON object with the mandatory `_type` field:

```json
{"_type": "ChatRequest", "rid": "7", "message": "Hello", "whisper_target_id": null}
```

- **The server's first frame** is always `SessionMetadata` (or `Error` if the bot is not
  accepted).
- **A request** from the bot carries `rid`: a string with the request's number. The numbers grow
  from 1.
- **A response** from the server repeats the request's `rid`. The type of the response is got by
  replacing `Request` with `Response` (`ChatRequest` → `ChatResponse`). The response is empty if
  the request returns nothing.
- **An event** is a frame without `rid`: the server sends it by itself.
- **An error** is an `Error` frame with the text `message`. If it has a `rid`, it is a refusal of
  a particular request (`ResponseError`). If there is no `rid`, it is a message about the
  connection: with the flag `do_not_reconnect: true` the connection has ended for good.
- **Keepalive** is `{"_type": "KeepaliveRequest"}` without `rid`, every 20 seconds. The server
  answers with `KeepaliveResponse`; the SDK takes it as a sign that the connection is alive.
  Keepalive does not count towards the limits. If no frame at all comes from the server for longer
  than three keepalive intervals, the SDK considers the connection lost and connects again.

Frame size: the server accepts frames up to 64 KiB, the SDK accepts up to 256 KiB.

### `SessionMetadata`

```json
{
  "_type": "SessionMetadata",
  "user_id": "…",
  "room_info": {"owner_id": "…", "room_name": "…"},
  "rate_limits": {"chat": [20, 10], "info": [30, 10]},
  "connection_id": "…",
  "sdk_version": null
}
```

`rate_limits` is "category → [requests, seconds]". It is parsed into `SessionMetadata` (see
[the models](models.md#sessionmetadata)).

### `Error`

```json
{"_type": "Error", "message": "the room is full", "do_not_reconnect": true}
```

The `do_not_reconnect` field is optional: without it the refusal is temporary. With a `rid` it is
the refusal of a request:
`{"_type": "Error", "message": "The message is empty", "rid": "7"}`.

## Requests

The table corresponds to the methods of [`BotAPI`](api.md). "Limit" is the rate category.

| Method | Request type | Limit | Request fields | Response |
|---|---|---|---|---|
| `chat` | `ChatRequest` | `chat` | `message`, `whisper_target_id: null` | `ChatResponse` |
| `whisper` | `ChatRequest` | `chat` | `message`, `whisper_target_id` | `ChatResponse` |
| `channel` | `ChannelRequest` | `channel` | `message`, `tags`, `only_to` | `ChannelResponse` |
| `emote` | `EmoteRequest` | `emote` | `emote_id`, `target_user_id` | `EmoteResponse` |
| `react` | `ReactionRequest` | `emote` | `reaction`, `target_user_id` | `ReactionResponse` |
| `move_to` | `FloorHitRequest` | `move` | `destination` (`x`, `y`, `z`, `facing`) | `FloorHitResponse` |
| `sit_on` | `AnchorHitRequest` | `move` | `anchor` (`entity_id`, `anchor_ix`) | `AnchorHitResponse` |
| `teleport_user` | `TeleportRequest` | `teleport` | `user_id`, `destination` | `TeleportResponse` |
| `list_room_users` | `GetRoomUsersRequest` | `info` | — | `GetRoomUsersResponse` (`content`: pairs of "user, position") |
| `privileges` | `GetRoomPrivilegeRequest` | `info` | `user_id` | `GetRoomPrivilegeResponse` (`content`: `moderator`, `designer`) |
| `set_privileges` | `ChangeRoomPrivilegeRequest` | `moderate` | `user_id`, `permissions` (`moderator`, `designer`) | `ChangeRoomPrivilegeResponse` (always a refusal on SukaRise) |
| `moderate`, `kick`, `ban`, `unban`, `mute` | `ModerateRoomRequest` | `moderate` | `user_id`, `moderation_action`, `action_length` | `ModerateRoomResponse` |
| `tip` | `TipUserRequest` | `tip` | `user_id`, `gold_bar` | `TipUserResponse` (`result`: `success` or `insufficient_funds`) |
| `buy_item` | `BuyItemRequest` | `shop` | `item_id` | `BuyItemResponse` (`result`) |
| `conversations` | `GetConversationsRequest` | `info` | `not_joined`, `last_id` | `GetConversationsResponse` (`conversations`, `not_joined`) |
| `messages` | `GetMessagesRequest` | `info` | `conversation_id`, `last_message_id` | `GetMessagesResponse` (`messages`) |
| `send_message` | `SendMessageRequest` | `message` | `conversation_id`, `content`, `type: "text"` | `SendMessageResponse` |
| `send_bulk_message` | `SendBulkMessageRequest` | `message` | `user_ids`, `content`, `type: "text"` | `SendBulkMessageResponse` |
| `leave_conversation` | `LeaveConversationRequest` | `message` | `conversation_id` | `LeaveConversationResponse` |
| `wallet`, `gold` | `GetWalletRequest` | `info` | — | `GetWalletResponse` (`content`: `type`, `amount`) |
| `outfit_of` | `GetUserOutfitRequest` | `info` | `user_id` | `GetUserOutfitResponse` (`outfit`) |
| `inventory` | `GetInventoryRequest` | `info` | — | `GetInventoryResponse` (`items`) |
| `wear` | `SetOutfitRequest` | `info` | `outfit` (items) | `SetOutfitResponse` |

A position (`destination`, `position`) is an object `{"x": 1.0, "y": 0.0, "z": 2.0, "facing":
"FrontRight"}`; a seat on furniture is `{"entity_id": "…", "anchor_ix": 0}`. An item is
`{"type": "clothing", "amount": 1, "id": "…", "account_bound": false, "active_palette": null}`.

## Events

| Frame type | Subscription | Fields | SDK class |
|---|---|---|---|
| `ChatEvent` | `chat` | `user`, `message`, `whisper` | `ChatEvent` |
| `EmoteEvent` | `emote` | `user`, `emote_id`, `receiver` | `EmoteEvent` |
| `ReactionEvent` | `reaction` | `user`, `reaction`, `receiver` | `ReactionEvent` |
| `UserJoinedEvent` | `user_joined` | `user`, `position` | `UserJoinedEvent` |
| `UserLeftEvent` | `user_left` | `user` | `UserLeftEvent` |
| `UserMovedEvent` | `user_moved` | `user`, `position` | `UserMovedEvent` |
| `ChannelEvent` | `channel` | `sender_id`, `msg`, `tags` | `ChannelEvent` |
| `RoomModeratedEvent` | `moderation` | `moderatorId`, `targetUserId`, `moderationType`, `duration` | `ModerationEvent` |
| `TipReactionEvent` | `tip_reaction` | `sender`, `receiver`, `item` | `TipEvent` |
| `MessageEvent` | `message` | `user_id`, `conversation_id`, `is_new_conversation` | `MessageEvent` |

A user in an event is `{"id": "…", "username": "…"}`. In `TipReactionEvent.item` gold is
`{"type": "gold", "amount": 10}` and a thing is a full item object with an `id`; the SDK tells
them apart by the presence of `id`. The non-standard field names (`msg`, `moderatorId`) are
inherited from the official protocol.

The SDK skips frames of unknown types: new server events do not break old bots. A frame of a
known type with wrong fields is dropped with a warning in the log.

## Limits

For every connection the server keeps a "bucket" per category and answers with the refusal
`Rate limit exceeded for <category> requests` if it is empty. The SDK keeps the same "buckets"
from the values in `SessionMetadata.rate_limits` and waits by itself, so it does not usually come
to a refusal; if one does happen (network delays squeezed the gaps), the SDK repeats the request
up to three times: it did not run. More in [How the SDK works](architecture.md#rate-limits).

Additional limits of the gateway: a chat line is up to 500 characters; a direct message up to
1000; a channel message up to 1024 bytes, up to 10 tags of 32 bytes and up to 50 addressees; an
emote identifier up to 96 bytes, a furniture identifier in `sit_on` up to 128 (the seat number is
0…255), an item identifier in `buy_item` up to 256, a conversation identifier up to 128; an
outfit has 1 to 64 items; coordinates are within ±1000; the term of a moderation action is up to
30 days; a request with an unsupported message `type` is refused (the bot sends only `text`). A
bot that falls so far behind that the gateway's send queue overflows is disconnected.

## One connection: one bot in one room

If a bot connects while an old connection with the same token is still open, the new one wins:
the old one gets an `Error` with `do_not_reconnect: true`. A bot can be in only one room at a
time, and a room can hold no more than three bots.
