**English** | [Русский](../ru/api.md) | [Português (Brasil)](../pt-BR/api.md)

# `BotAPI` reference

Everything a bot can do is a method of the `BotAPI` object. In a running bot it is available as
`self.api`, and in a command also as `ctx.api`. Each method is **one asynchronous action**: call
it with `await`.

```python
await self.api.chat("Hello!")
users = await self.api.list_room_users()
```

## General rules

**Checked before sending.** Arguments are checked in advance. Empty text, an unknown reaction, a
coordinate outside the allowed range, a seat number outside 0…255 or an identifier longer than
the server's limit (an emote: 96 bytes, furniture and a conversation: 128, an item: 256) raise
`InvalidArgument` on your line of code, and the request is not sent.

**Exceptions.** Any method may raise:

| Exception | When |
|---|---|
| `InvalidArgument` | an argument is wrong; the request was not sent |
| `ResponseError` | the server refused (no rights, the person is not in the room, and so on); the refusal text is in `error.message`, in English |
| `RateLimited` | the server refused because of the rate limit and the SDK's retries did not help (a subclass of `ResponseError`) |
| `NotConnected` | the bot has no connection |
| `RequestTimeout` | the server did not answer within 10 seconds |

The tables below list only the causes specific to a method. For details see
[Errors and refusals](errors.md).

**Rate limits.** Every method has a limit category (the "Limit" column). If the budget is spent,
the SDK waits by itself; a bot does not usually see a refusal for the limit. See
[How the SDK works](architecture.md#rate-limits).

**2D and 3D.** A bot works in ordinary (2D) rooms and in 3D rooms. The "Rooms" column shows
where a method is available; in a 3D world the bot gets the same as in 2D, except people's
reactions, which the client does not send there (see
[What works and what does not](../../README.md#what-works-and-what-does-not)).

## Summary

| Method | What it does | Limit | Rooms |
|---|---|---|---|
| [`chat(message)`](#chat) | say something in the public chat | `chat` | 2D, 3D |
| [`whisper(user_id, message)`](#whisper) | whisper to one person | `chat` | 2D, 3D |
| [`channel(message, tags, only_to)`](#channel) | a hidden message to other bots | `channel` | 2D, 3D |
| [`emote(emote_id, target_user_id)`](#emote) | play an emote | `emote` | 2D, 3D |
| [`react(reaction, target_user_id)`](#react) | send a reaction | `emote` | 2D, 3D |
| [`move_to(position)`](#move_to) | walk to a point | `move` | 2D, 3D |
| [`sit_on(anchor)`](#sit_on) | sit on a furniture seat | `move` | 2D, 3D |
| [`teleport_user(user_id, position)`](#teleport_user) | move a person | `teleport` | 2D, 3D |
| [`list_room_users()`](#list_room_users) | who is in the room and where | `info` | 2D, 3D |
| [`privileges(user_id)`](#privileges) | a person's rights in the room | `info` | 2D, 3D |
| [`set_privileges(user_id, moderator, designer)`](#set_privileges) | grant/revoke rights | `moderate` | always refused on SukaRise |
| [`moderate(user_id, action, seconds)`](#moderate) | kick/ban/unban/mute | `moderate` | 2D, 3D |
| [`kick(user_id)`](#kick) | kick | `moderate` | 2D, 3D |
| [`ban(user_id, seconds)`](#ban) | ban | `moderate` | 2D, 3D |
| [`unban(user_id)`](#unban) | lift a ban | `moderate` | 2D, 3D |
| [`mute(user_id, seconds)`](#mute) | mute | `moderate` | 2D, 3D |
| [`tip(user_id, gold_bar)`](#tip) | a tip in the bot's gold | `tip` | 2D, 3D |
| [`buy_item(item_id)`](#buy_item) | buy an item with the bot's gold | `shop` | 2D, 3D |
| [`conversations(not_joined, last_id)`](#conversations) | the bot's direct conversations | `info` | 2D, 3D |
| [`messages(conversation_id, last_message_id)`](#messages) | a conversation's messages | `info` | 2D, 3D |
| [`send_message(conversation_id, content)`](#send_message) | reply in a conversation | `message` | 2D, 3D |
| [`send_bulk_message(user_ids, content)`](#send_bulk_message) | write to many | `message` | 2D, 3D |
| [`leave_conversation(conversation_id)`](#leave_conversation) | leave a conversation | `message` | 2D, 3D |
| [`wallet()`](#wallet) | all the bot's currencies | `info` | 2D, 3D |
| [`gold()`](#gold) | the bot's gold | `info` | 2D, 3D |
| [`outfit_of(user_id)`](#outfit_of) | a person's outfit | `info` | 2D, 3D |
| [`inventory()`](#inventory) | the bot's wardrobe | `info` | 2D, 3D |
| [`wear(items)`](#wear) | change the bot's outfit | `info` | 2D, 3D |
| [`split_message(text, limit)`](#split_message) | split a long text | — | a helper function |

## Chat

### `chat`

```python
async def chat(self, message: str) -> None
```

Say a line in the room's public chat. Text longer than **500 characters** is split at spaces and
goes out as several messages in a row.

| Parameter | Description |
|---|---|
| `message` | the text of the line |

`InvalidArgument`: the text is empty or only spaces. `ResponseError`: for example, the bot was
muted.

```python
await self.api.chat("Hello, everyone!")
```

### `whisper`

```python
async def whisper(self, user_id: str, message: str) -> None
```

A private message to one person **in the room**. Only the recipient and the bot see it. Long
text is split into several whispers.

| Parameter | Description |
|---|---|
| `user_id` | the recipient; must be in the room |
| `message` | the text |

`ResponseError`: the recipient is not in the room. For messages to people who are not in the room
use direct conversations ([`send_message`](#send_message)).

### `channel`

```python
async def channel(
    self,
    message: str,
    *,
    tags: Iterable[str] = (),
    only_to: Iterable[str] | None = None,
) -> None
```

A hidden message to other **bots** in this room. Players do not see it. The recipients hear it in
[`on_channel`](handlers.md#on_channel); the sender does not receive its own message. This is how
bots in one room can agree among themselves.

| Parameter | Description |
|---|---|
| `message` | the text, at most **1024 bytes** in UTF-8 |
| `tags` | tags, up to 10 of them, each at most **32 bytes** in UTF-8 (a Cyrillic letter takes two bytes); recipients use them to pick messages |
| `only_to` | identifiers of the addressee bots (up to 50); `None`: all the bots of the room |

## Body language

### `emote`

```python
async def emote(self, emote_id: str, *, target_user_id: str | None = None) -> None
```

Play an emote: by itself or towards a person. **A bot plays paid emotes for free if its owner
has an active PREMIUM.** Paired emotes (with a partner) are not available to a bot.

| Parameter | Description |
|---|---|
| `emote_id` | the emote's identifier, for example `"emote-wave"`, at most 96 bytes |
| `target_user_id` | whom to aim it at; `None`: at no one. The addressee must be in the room (in 3D too); as in 2D, the event of the emote does not carry them |

`ResponseError`: there is no such emote, it is a paired one, it is a paid one and the owner has
no PREMIUM, or the addressee is not in the room.

### `react`

```python
async def react(self, reaction: Reaction, target_user_id: str) -> None
```

Send a person a reaction: `"clap"` (applause), `"heart"` (a heart), `"thumbs"` (a thumbs up),
`"wave"` (a greeting), `"wink"` (a wink).

`InvalidArgument`: an unknown reaction. `ResponseError`: the addressee is not in the room.

```python
await self.api.react("heart", user.id)
```

## Movement

### `move_to`

```python
async def move_to(self, position: Position) -> None
```

Send the bot walking to a point on the floor. The coordinates are finite numbers within
**±1000**; the `facing` direction is `FrontRight`, `FrontLeft`, `BackRight` or `BackLeft`.

```python
from sukarisebot import Position

await self.api.move_to(Position(5.5, 0.0, 5.5, facing="FrontLeft"))
```

**In a 3D world a walk has no answer.** The request goes out and counts as done even if the
world cannot lay a path (a point behind furniture or off the floor): the bot then simply stays
where it is and no `ResponseError` comes. If it matters whether the bot arrived, read its
position (`list_room_users`) a second or two later and, if it failed, try another point nearby.

### `sit_on`

```python
async def sit_on(self, anchor: AnchorPosition) -> None
```

Seat the bot on a seat of a piece of furniture. Take the furniture's identifier and the seat
number (`entity_id`, `anchor_ix`) from the position of a person who is sitting on that
furniture: for someone sitting, `location` is an `AnchorPosition`. The furniture identifier is at
most 128 bytes, the seat number is an integer from 0 to 255.

```python
from sukarisebot import AnchorPosition, Bot, Location, User


class Follower(Bot):
    async def on_user_move(self, user: User, position: Location) -> None:
        if isinstance(position, AnchorPosition):
            await self.api.sit_on(position)
```

`ResponseError`: there is no such seat or it is taken. In a 3D world the bot first walks to the
seat: if the world did not seat it within 8 seconds, that is the refusal "The bot could not
reach that seat", and the bot stays where it stood.

### `teleport_user`

```python
async def teleport_user(self, user_id: str, position: Position) -> None
```

Instantly move a person to a point on the floor. **Moderator rights are needed** in the room:
designer rights alone are not enough. The bot obeys the same rules as a human moderator.

## The room and rights

### `list_room_users`

```python
async def list_room_users(self) -> list[RoomUser]
```

Who is in the room now and where they stand or sit. You usually do not need to call it by hand:
the roster is kept by [`bot.room`](tools.md#the-room-roster-botroom). It returns a list of
`RoomUser` (`.user`, `.location`).

### `privileges`

```python
async def privileges(self, user_id: str) -> RoomPermissions
```

A person's rights in this room: `.moderator`, `.designer`. `None` in a field means the server
did not say.

```python
permissions = await self.api.privileges(user.id)
if permissions.moderator:
    ...
```

### `set_privileges`

```python
async def set_privileges(
    self,
    user_id: str,
    *,
    moderator: bool | None = None,
    designer: bool | None = None,
) -> None
```

Grant or revoke moderator and designer rights (`None`: leave unchanged).

> **On the SukaRise server bots cannot change rights**: only the room's owner and the staff can.
> The call always ends in a `ResponseError`. The method is kept for compatibility with code
> written for the official Highrise SDK.

## Moderation

For moderation the bot must have **moderator rights** in the room: the "designer" right, which
is enough to enter, is not suitable. The bot obeys the same rules as a person: the room's owner
cannot be punished, and a moderator can be punished only by the owner. The actions are available
in both 2D and 3D rooms.

### `moderate`

```python
async def moderate(self, user_id: str, action: ModerationAction, *, seconds: int | None = None) -> None
```

Kick, ban, unban or mute.

| Parameter | Description |
|---|---|
| `user_id` | whom to apply it to |
| `action` | `"kick"`, `"ban"`, `"unban"` or `"mute"` |
| `seconds` | the term of a ban or mute, from 0 to 2,592,000 (30 days); `None`: no term given, the server decides |

`InvalidArgument`: an unknown action or a term out of range. `ResponseError`: no moderator rights
or the target is protected. The short forms follow.

### `kick`

```python
async def kick(self, user_id: str) -> None
```

Kick from the room. The same as `moderate(user_id, "kick")`.

### `ban`

```python
async def ban(self, user_id: str, *, seconds: int | None = None) -> None
```

Ban. The same as `moderate(user_id, "ban", seconds=seconds)`.

### `unban`

```python
async def unban(self, user_id: str) -> None
```

Lift a ban or a mute. The same as `moderate(user_id, "unban")`.

### `mute`

```python
async def mute(self, user_id: str, seconds: int) -> None
```

Mute for a term: the person cannot write in the chat. The same as
`moderate(user_id, "mute", seconds=seconds)`.

```python
from sukarisebot import Bot, ResponseError, User


class Guard(Bot):
    async def on_chat(self, user: User, message: str) -> None:
        if "spam" in message.lower():
            try:
                await self.api.mute(user.id, 60)
            except ResponseError:
                await self.api.chat("I cannot mute: I have no moderator rights.")
```

## Tips and purchases

### `tip`

```python
async def tip(self, user_id: str, gold_bar: GoldBar) -> bool
```

Give a person in the room a tip as a gold bar **from the bot's wallet**. It returns `True` if the
tip was sent and `False` if the bot does not have enough gold (this is an answer, not an error;
nothing is charged). The sender pays slightly more than the addressee receives: for example, 11
gold for `gold_bar_10`.

The allowed bars (`GoldBar`): `gold_bar_1`, `gold_bar_5`, `gold_bar_10`, `gold_bar_50`,
`gold_bar_100`, `gold_bar_500`, `gold_bar_1k`, `gold_bar_5000`, `gold_bar_10k`; the number is how
much gold the addressee gets. The addressee must be in the room.

```python
paid = await self.api.tip(user.id, "gold_bar_10")
if not paid:
    await self.api.chat("Not enough gold :(")
```

### `buy_item`

```python
async def buy_item(self, item_id: str) -> bool
```

Buy an item in the shop **with the bot's gold**. Bots can buy only items the shop sells for
gold. It returns `True` if bought and `False` if there was not enough gold. What was bought
appears in [`inventory`](#inventory). The identifier is at most 256 bytes; spaces at the ends
are dropped.

## Direct messages

Direct messages are conversations outside the room. A person writes to the bot through the
game's ordinary interface; the conversation request is accepted for the bot at once. The bot
**replies** in conversations it is already in and does not start them. The bot takes part only
in direct conversations (not in groups) and sends only text. The flow:
[`on_message`](handlers.md#on_message) reports a new message → [`messages`](#messages) reads →
[`send_message`](#send_message) replies.

### `conversations`

```python
async def conversations(self, *, not_joined: bool = False, last_id: str | None = None) -> ConversationPage
```

The bot's direct conversations, 20 at a time. For the next page pass the identifier of the
current page's last conversation in `last_id`. `not_joined=True` shows requests not yet
accepted; since requests are accepted for the bot at once, there are usually none.

### `messages`

```python
async def messages(self, conversation_id: str, *, last_message_id: str | None = None) -> list[DirectMessage]
```

A conversation's messages, **newest first**, 20 at a time. Reading the newest page marks the
conversation as read. To go back in time, pass the identifier of the oldest message you have in
`last_message_id`.

### `send_message`

```python
async def send_message(self, conversation_id: str, content: str) -> None
```

Reply in a conversation. Text longer than **1000 characters** is split into several messages.

### `send_bulk_message`

```python
async def send_bulk_message(self, user_ids: Sequence[str], content: str) -> None
```

Write to **up to 100** people at once, but only to those the bot already has a conversation with
(who wrote to it). The message does not go to the others; if it reached no one, that is a
refusal. The text is at most 1000 characters (it is not split here).

### `leave_conversation`

```python
async def leave_conversation(self, conversation_id: str) -> None
```

Leave a conversation.

## Wallet, wardrobe and inventory

### `wallet`

```python
async def wallet(self) -> list[CurrencyItem]
```

All the bot's currencies. Gold is the element with `type == "gold"`.

### `gold`

```python
async def gold(self) -> int
```

The bot's gold (0 if there is none). A convenient wrapper over `wallet()`. The bot receives gold
as tips; the owner collects it in the personal cabinet, on the bot's card.

### `outfit_of`

```python
async def outfit_of(self, user_id: str) -> list[Item]
```

What a person (or the bot itself) is wearing now. The bot can find out its own outfit with
`await self.my_outfit()` as well.

### `inventory`

```python
async def inventory(self) -> list[Item]
```

The clothes the bot owns.

### `wear`

```python
async def wear(self, items: Sequence[Item]) -> None
```

Replace the bot's outfit as a whole, 1 to 64 items. Before sending, the SDK checks the outfit
([`outfit_problems`](tools.md#the-outfit-outfit_problems-and-category_of)): every item is
clothing, there are no repeats, each basic category occurs once, the body parts are present and
the body is covered. The SDK does not classify items with identifiers `bag-…` (the server
determines their type from the catalog, and it can be anything, for example an eyebrow), so they
may make up for what is missing. Then the server checks the outfit. While the bot's owner has an
active PREMIUM, changing the outfit is **free**: the bot can put on any item of the catalog and
does not need to buy it. The owner can write `myoutfit` to the bot in the chat or as a whisper,
and the bot puts on *the owner's current outfit*.

`InvalidArgument`: the outfit breaks the rules (the reasons are listed in the text).
`ResponseError`: the owner has no PREMIUM, or the outfit has an item that is not in the catalog.

```python
from sukarisebot import Bot, Context, command


class Mirror(Bot):
    @command("copyme", description="put on my outfit")
    async def copyme(self, ctx: Context) -> None:
        outfit = await ctx.api.outfit_of(ctx.user.id)
        await ctx.api.wear(outfit)
        await ctx.reply("Done!")
```

## A helper function

### `split_message`

```python
def split_message(text: str, limit: int = 500) -> list[str]
```

Splits text into pieces of at most `limit` characters, at spaces where possible; the spaces at the
joins are dropped. If there is no space within `limit`, the word is cut exactly at `limit`.
`chat` and `send_message` split long text in the same way. You need to call it by hand only if
you want to send the pieces with pauses or to different places.
