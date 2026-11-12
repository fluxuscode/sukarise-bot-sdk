**English** | [Русский](../ru/models.md) | [Português (Brasil)](../pt-BR/models.md)

# Data models

All the data the SDK passes to your code consists of **immutable dataclasses** (`frozen=True`,
`slots=True`). They cannot be changed after creation, so they are safe to store, to compare
(`==`) and to use as dictionary keys. The field names match the official Highrise SDK, so code
written for that SDK reads the same.

All the classes are imported from the package: `from sukarisebot import User, Position, ChatEvent`.

## Allowed values (literals)

The editor suggests these values and a type checker (mypy, pyright) catches typos. Next to each
literal there is a set with the same values for checks at run time.

| Type | Values | Set |
|---|---|---|
| `Facing` | `"FrontRight"`, `"FrontLeft"`, `"BackRight"`, `"BackLeft"` | `FACINGS` |
| `Reaction` | `"clap"`, `"heart"`, `"thumbs"`, `"wave"`, `"wink"` | `REACTIONS` |
| `GoldBar` | `"gold_bar_1"`, `"gold_bar_5"`, `"gold_bar_10"`, `"gold_bar_50"`, `"gold_bar_100"`, `"gold_bar_500"`, `"gold_bar_1k"`, `"gold_bar_5000"`, `"gold_bar_10k"` | `GOLD_BARS` |
| `ModerationAction` | `"kick"`, `"ban"`, `"unban"`, `"mute"` | `MODERATION_ACTIONS` |

## People and places

### `User`

A SukaRise user: a player or another bot.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | the account's permanent identifier; it does not change when the name changes |
| `username` | `str` | the in-game name at the moment of the event |

Compare people by `id`, not by `username`: the name can be changed.

### `Position`

A point on the room's floor and a facing direction.

| Field | Type | Description |
|---|---|---|
| `x` | `float` | the coordinate along the X axis |
| `y` | `float` | the height above the floor; `0.0` for an ordinary floor |
| `z` | `float` | the coordinate along the Z axis |
| `facing` | `Facing` | where the character looks; `"FrontRight"` by default |

Finite numbers within ±1000 are allowed.

### `AnchorPosition`

A seat on a piece of furniture.

| Field | Type | Description |
|---|---|---|
| `entity_id` | `str` | the identifier of the piece of furniture in the room |
| `anchor_ix` | `int` | the number of the seat on this piece, from 0 to 255 |

### `Location`

`Location = Position | AnchorPosition` is **where a user is**: standing on the floor or sitting
on furniture. Tell the variants apart with `isinstance` or `match`:

```python
from sukarisebot import AnchorPosition, Location, Position


def describe(location: Location) -> str:
    match location:
        case Position(x=x, z=z):
            return f"standing at ({x:.1f}, {z:.1f})"
        case AnchorPosition(entity_id=furniture, anchor_ix=place):
            return f"sitting on {furniture}, seat {place}"
```

### `RoomUser`

A person (or a bot) in the room. The elements of `list_room_users()` and `bot.room.users()`.

| Field | Type | Description |
|---|---|---|
| `user` | `User` | who it is |
| `location` | `Location` | where they are |

### `RoomInfo`

Information about the bot's room.

| Field | Type | Description |
|---|---|---|
| `owner_id` | `str` | the identifier of the room's owner |
| `room_name` | `str` | the room's name |

### `RoomPermissions`

A user's rights in the room.

| Field | Type | Description |
|---|---|---|
| `moderator` | `bool \| None` | whether they can moderate; `None`: the server did not say |
| `designer` | `bool \| None` | whether they can edit the room; `None`: the server did not say |

## Things and money

### `CurrencyItem`

An amount in one currency: a wallet line or a tip in gold.

| Field | Type | Description |
|---|---|---|
| `type` | `str` | the currency's name; gold is `"gold"` |
| `amount` | `int` | the quantity |

### `Item`

An item: a piece of clothing in the wardrobe or the outfit.

| Field | Type | Description |
|---|---|---|
| `type` | `str` | the kind of item; `"clothing"` for clothes |
| `amount` | `int` | the quantity; 1 for clothes |
| `id` | `str` | the item's identifier in the catalog, for example `shirt-n_plaid_blackwhite` |
| `account_bound` | `bool` | the item is bound to the account and is not passed to others (`False` by default) |
| `active_palette` | `int \| None` | the number of the chosen colour palette or `None` |

## Events

Events arrive in the [`on_...`](handlers.md) handlers. They are all united in the type `Event`:
`ChatEvent | EmoteEvent | ReactionEvent | UserJoinedEvent | UserLeftEvent |
UserMovedEvent | ChannelEvent | ModerationEvent | TipEvent | MessageEvent`. It is needed for type
hints (`wait_for`, `on_error`) and for taking events apart with `match`.

| Class | Fields | Which handler |
|---|---|---|
| `ChatEvent` | `user: User`, `message: str`, `whisper: bool` | `on_chat` / `on_whisper` |
| `EmoteEvent` | `user: User`, `emote_id: str`, `receiver: User \| None` | `on_emote` |
| `ReactionEvent` | `user: User`, `reaction: str`, `receiver: User` | `on_reaction` |
| `UserJoinedEvent` | `user: User`, `position: Location` | `on_user_join` |
| `UserLeftEvent` | `user: User` | `on_user_leave` |
| `UserMovedEvent` | `user: User`, `position: Location` | `on_user_move` |
| `ChannelEvent` | `sender_id: str`, `message: str`, `tags: tuple[str, ...]` | `on_channel` |
| `ModerationEvent` | `moderator_id: str`, `target_user_id: str`, `moderation_type: str`, `duration: int \| None` | `on_moderate` |
| `TipEvent` | `sender: User`, `receiver: User`, `item: Item \| CurrencyItem` | `on_tip` |
| `MessageEvent` | `user_id: str`, `conversation_id: str`, `is_new_conversation: bool` | `on_message` |

Notes:

- `ReactionEvent.reaction` and `ModerationEvent.moderation_type` are ordinary strings, not
  literals: that way the SDK does not break if the server adds a new value.
- `TipEvent.item` is a `CurrencyItem` for gold and an `Item` for a thing. A tip to a bot always
  arrives as gold.
- `ModerationEvent.duration` is the term in seconds; `None` if no term was given.
- `MessageEvent` carries no text: the message is read with `api.messages(conversation_id)`.

## Direct messages

### `DirectMessage`

One message of a direct conversation.

| Field | Type | Description |
|---|---|---|
| `message_id` | `str` | the message's identifier; good for paging backwards |
| `conversation_id` | `str` | the conversation the message belongs to |
| `created_at` | `str \| None` | the time of sending in the form the server sent it |
| `content` | `str` | the text of the message |
| `sender_id` | `str` | the sender's identifier |
| `category` | `str` | the kind of message: `text` or `invite` (an invitation) |

### `Conversation`

A direct conversation of the bot. Bots take part only in direct conversations.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | the conversation's identifier |
| `did_join` | `bool` | whether the bot accepted the conversation (requests are accepted for the bot at once) |
| `unread_count` | `int` | how many messages the bot has not read yet |
| `last_message` | `DirectMessage \| None` | the last message |
| `muted` | `bool` | whether the conversation's notifications are off |
| `member_ids` | `tuple[str, ...]` | the participants' identifiers |
| `owner_id` | `str \| None` | the conversation's creator |

### `ConversationPage`

A page of the bot's conversations: up to 20.

| Field | Type | Description |
|---|---|---|
| `conversations` | `tuple[Conversation, ...]` | the page's conversations |
| `not_joined` | `int` | how many conversation requests the bot has not accepted yet; usually 0 |

## Session and limits

### `SessionMetadata`

The first frame of an accepted connection. It arrives in `on_start` and is available as
`bot.session`.

| Field | Type | Description |
|---|---|---|
| `user_id` | `str` | the identifier of the bot's own account |
| `room_info` | `RoomInfo` | the room the bot entered |
| `rate_limits` | `dict[str, RateLimit]` | the rate limits per category |
| `connection_id` | `str` | the identifier of this connection (for logs) |

### `RateLimit`

The rate limit for one category: at most `requests` requests per `seconds` seconds.

| Field | Type | Description |
|---|---|---|
| `requests` | `int` | how many requests are allowed |
| `seconds` | `float` | in what window of time |

## Constants

Besides the types, the package exports constants that the SDK itself and your checks use:
`FACINGS`, `REACTIONS`, `GOLD_BARS`, `MODERATION_ACTIONS` (sets of allowed values),
`DEFAULT_URL` (the default gateway address) and `ENV_TOKEN`, `ENV_ROOM_ID`, `ENV_URL` (the names
of the environment variables).
