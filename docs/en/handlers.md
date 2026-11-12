**English** | [Русский](../ru/handlers.md) | [Português (Brasil)](../pt-BR/handlers.md)

# Event handlers

A handler is a method of the bot's class of the form `async def on_...`. All of them are defined
in `Bot` and **do nothing by default**, so you override only the ones you need.

```python
from sukarisebot import Bot, Location, User


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Hello, {user.username}!")
```

Rules common to all handlers:

- The method must be `async def`. Take the signature from the table below; in PyCharm it is
  generated, together with its description, by **Code → Override Methods** (`Ctrl+O`).
- The SDK subscribes the bot **only to the events that have an overridden handler**, plus the
  chat and people joining and leaving (commands and `bot.room` need them). No extra traffic
  arrives. More in [How the SDK works](architecture.md#event-subscriptions).
- Events are handled **one at a time, in order of arrival**. Until a handler has finished, the
  next event waits. Move long work into tasks.
- An exception inside a handler does not stop the bot: it is passed to `on_error`.
- The signature must not be changed: the SDK calls handlers with positional arguments in the
  order given here.

## Summary table

| Handler | When it is called | Event | Subscription | In 3D |
|---|---|---|---|---|
| [`on_start(session)`](#on_start) | the bot entered the room; again after every reconnection | `SessionMetadata` | — | yes |
| [`on_chat(user, message)`](#on_chat) | a line in the public chat | `ChatEvent` | `chat` | yes |
| [`on_whisper(user, message)`](#on_whisper) | a whisper addressed to the bot | `ChatEvent` | `chat` | yes |
| [`on_emote(user, emote_id, receiver)`](#on_emote) | someone played an emote | `EmoteEvent` | `emote` | yes |
| [`on_reaction(user, reaction, receiver)`](#on_reaction) | one player sent a reaction to another | `ReactionEvent` | `reaction` | no |
| [`on_user_join(user, position)`](#on_user_join) | someone entered the room | `UserJoinedEvent` | `user_joined` | yes |
| [`on_user_leave(user)`](#on_user_leave) | someone left | `UserLeftEvent` | `user_left` | yes |
| [`on_user_move(user, position)`](#on_user_move) | someone walked or sat down (in 3D: walked) | `UserMovedEvent` | `user_moved` | yes |
| [`on_channel(sender_id, message, tags)`](#on_channel) | a hidden message from another bot | `ChannelEvent` | `channel` | yes |
| [`on_moderate(moderator_id, target_user_id, moderation_type, duration)`](#on_moderate) | moderation in the room | `ModerationEvent` | `moderation` | yes |
| [`on_tip(sender, receiver, item)`](#on_tip) | a tip in the room | `TipEvent` | `tip_reaction` | yes |
| [`on_message(user_id, conversation_id, is_new_conversation)`](#on_message) | a person wrote the bot a direct message | `MessageEvent` | `message` | yes |
| [`on_error(error, event)`](#on_error) | a handler, command or timer failed | — | — | — |

The subscriptions `chat`, `user_joined` and `user_left` are always on (the last two except in
"clean room" mode): commands do not work without the chat, and `bot.room` does not without joins
and leaves.

In a 3D room the bot receives the events marked "yes" in the last column: chat and whispers,
people joining and leaving, people's walks and emotes, moderation, hidden messages from other
bots, and direct messages. People's reactions do not reach the bot in 3D: the 3D client does not
send them. People's tips do reach it in 3D. The bot learns people's positions from walk events
and with the `list_room_users()` request (or `await self.refresh_room()`).

## Each handler in detail

### `on_start`

```python
async def on_start(self, session: SessionMetadata) -> None
```

The bot has entered the room. It is called **after every (re)connection**, so write it so that a
repeated call does no harm (for example, do not start endless loops here). By this moment
`bot.room` is already filled (unless "clean room" mode is on). A good place for a greeting and
for first-time setup.

- `session`: who the bot is (`session.user_id`), which room it is in
  (`session.room_info.room_name`, `.owner_id`) and which rate limits apply.

### `on_chat`

```python
async def on_chat(self, user: User, message: str) -> None
```

A line in the room's public chat. It is called for any line, including command messages
(`!roll`): the command runs separately, after this handler. The server does not send the bot its
own lines in a 2D room, and the SDK does not run commands written by the bot itself.

### `on_whisper`

```python
async def on_whisper(self, user: User, message: str) -> None
```

A whisper addressed to the bot (in the room). The bot does not see other people's whispers to
each other. Do not confuse it with direct messages in conversations: those arrive in
[`on_message`](#on_message).

### `on_emote`

```python
async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None
```

Someone played an emote. `receiver` is the person it is aimed at, or `None` if it is aimed at no
one.

### `on_reaction`

```python
async def on_reaction(self, user: User, reaction: str, receiver: User) -> None
```

One player sent another a reaction: `clap`, `heart`, `thumbs`, `wave` or `wink`. The `reaction`
parameter is an ordinary string (not a `Literal`): that way the code does not break if the
server ever adds a new reaction.

### `on_user_join`

```python
async def on_user_join(self, user: User, position: Location) -> None
```

A user entered the room. `position` is where they appeared: a `Position` (a point on the floor)
or an `AnchorPosition` (a seat on furniture).

### `on_user_leave`

```python
async def on_user_leave(self, user: User) -> None
```

A user left the room.

### `on_user_move`

```python
async def on_user_move(self, user: User, position: Location) -> None
```

A user walked to another point or sat down. In a busy room these events are frequent; subscribe
only if you need them.

### `on_channel`

```python
async def on_channel(self, sender_id: str, message: str, tags: tuple[str, ...]) -> None
```

A hidden message from another bot in this room (see [`BotAPI.channel`](api.md#channel)). Players
do not see such messages. The bot does not receive its own messages.

### `on_moderate`

```python
async def on_moderate(
    self,
    moderator_id: str,
    target_user_id: str,
    moderation_type: str,
    duration: int | None,
) -> None
```

A moderation action was carried out in the room: `moderation_type` is `kick`, `ban`, `unban` or
`mute`; `duration` is the term in seconds or `None`. The bot is not notified about actions it
carried out itself. If the bot itself is punished, `target_user_id` equals
`bot.session.user_id`.

### `on_tip`

```python
async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None
```

Someone tipped someone. **The event arrives for any tip in the room**, not only for tips to the
bot. A tip to the bot itself is one where `receiver.id == self.session.user_id`.

`item` is either a `CurrencyItem` (gold: `item.amount` is how much gold the addressee received)
or an `Item` (a thing). A tip to a bot always arrives **as gold**: the bar's value is credited to
the bot's wallet (`gold_bar_10` gives 10 gold). The owner collects the accumulated gold in the
personal cabinet. For an example see [`examples/tipping_bot.py`](../../examples/tipping_bot.py).

```python
from sukarisebot import Bot, CurrencyItem, Item, User


class Thanks(Bot):
    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        if self.session is None or receiver.id != self.session.user_id:
            return  # not a tip for the bot
        if isinstance(item, CurrencyItem):
            await self.api.chat(f"Thank you, {sender.username}, for {item.amount} gold!")
```

### `on_message`

```python
async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None
```

A person wrote the bot a **direct message** (in a conversation outside the room). The event has
no text: read it with `await self.api.messages(conversation_id)` (newest messages first) and
reply with `await self.api.send_message(conversation_id, "…")`.

- A conversation request is accepted for the bot automatically.
- The bot does not write first in a conversation: the person starts it.
- The bot takes part only in direct conversations (not in groups).

```python
from sukarisebot import Bot


class Echo(Bot):
    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        messages = await self.api.messages(conversation_id)
        if messages and messages[0].sender_id == user_id:
            await self.api.send_message(conversation_id, f"You wrote: {messages[0].content}")
```

### `on_error`

```python
async def on_error(self, error: Exception, event: Event | None) -> None
```

A handler, command or timer raised an exception. By default the error is written to the
`sukarisebot` log together with a traceback. Override the method to, for example, tell the
owner:

```python
from sukarisebot import Bot, Event


class Careful(Bot):
    async def on_error(self, error: Exception, event: Event | None) -> None:
        await super().on_error(error, event)  # keep the log entry
        if self.owner_id is not None and self.owner_id in self.room:
            await self.api.whisper(self.owner_id, f"Error: {error}")
```

`event` is the event during whose handling the error occurred. For a command it is the chat
event that called it; `None` for a timer and for an error in `on_start`. If `on_error` itself
fails, that goes to the log and the bot keeps working.

## Which event goes to which handler

The chat is split between two handlers: the same `ChatEvent` goes to `on_chat` if
`whisper=False` and to `on_whisper` if `whisper=True`. The other events are tied to handlers
one to one. In all cases commands (`@command`) run **after** the chat event's handler.

## What to do with an event that has no handler

Nothing: if a handler is not overridden, the SDK does not subscribe to that event and it does
not arrive at all (except the chat and joins and leaves, which always arrive). This also
concerns [`wait_for`](commands.md#dialogues-wait_for): the chat is always delivered (its
subscription is on for the sake of commands), and to wait for any other event, override its
handler: an empty one is enough (`async def on_emote(...): pass`), otherwise there is no
subscription and `wait_for` will not get its event.
