**English** | [Русский](../ru/testing.md) | [Português (Brasil)](../pt-BR/testing.md)

# Testing without a server

`Harness` runs a bot **in memory**: there is no network, no need to wait for timers, and the room
is imitated with prepared answers. You feed the bot events (`say`, `join`, `emit`) and then check
what the bot tried to do (`chats`, `whispers`, `requests`).

```python
import asyncio

from sukarisebot import Bot, Location, User
from sukarisebot.testing import Harness


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Welcome, {user.username}!")


def test_greeting() -> None:
    async def scenario() -> None:
        harness = Harness(Greeter())
        await harness.start()
        await harness.join("alice")
        assert harness.chats == ["Welcome, alice!"]

    asyncio.run(scenario())
```

The tests run with plain `pytest`. No extra plugins for asynchronous tests are needed: the
scenario is wrapped in `asyncio.run(...)`.

## How it works

`Harness` connects the bot not to a server but to a "recording server": `RecordingRequester`. All
the bot's actions (`self.api.chat(...)` and so on) do not go to the network but are recorded in
the list `harness.requester.sent`. The events you feed in take the same path as in a real
connection: first the `wait_for` waits fire, then the `on_...` handlers and the commands.

## Feeding events

| Method | What it does |
|---|---|
| `await harness.start()` | "Connects" the bot: calls `on_start`, loads the room roster (unless "clean room") |
| `await harness.say(username, text, whisper=False)` | a user writes in the chat (or whispers to the bot) |
| `await harness.join(username, position)` | a user enters: gets into the room roster and a `UserJoinedEvent` arrives |
| `await harness.leave(user)` | a user leaves |
| `await harness.emit(event)` | feed any event: `EmoteEvent`, `ModerationEvent`, `MessageEvent` and so on |
| `harness.event_tip(sender, receiver, item)` | build a `TipEvent` to feed through `emit` |

A user's identifier in a test is `"user-" + username`. Each call returns when the bot has finished
handling the event.

## Checking the result

| Member | What it returns |
|---|---|
| `harness.chats` | the bot's lines in the public chat, in order |
| `harness.whispers` | the bot's whispers, in order |
| `harness.requests("ModerateRoomRequest")` | all the requests of one kind (`Sent`) |
| `harness.requester.sent` | all the requests in order |
| `harness.bot` | the bot itself: check `bot.room`, `bot.state` and so on |

`Sent` is the record of one request: `kind` (for example, `"ChatRequest"`), `category` (the limit)
and `body` (the fields). Which requests each method sends is in [Protocol](protocol.md).

```python
import asyncio

from sukarisebot import Bot, Context, command
from sukarisebot.testing import Harness


class Guard(Bot):
    @command("kick", owner_only=True)
    async def kick(self, ctx: Context) -> None:
        name = ctx.arg(0)
        entry = None if name is None else self.room.find(name)
        if entry is not None:
            await self.api.kick(entry.user.id)


def test_kick_asks_the_server_to_kick() -> None:
    async def scenario() -> None:
        harness = Harness(Guard(), owner_id="user-boss")
        await harness.start()
        await harness.join("mallory")
        await harness.say("boss", "!kick mallory")
        (request,) = harness.requests("ModerateRoomRequest")
        assert request.body["user_id"] == "user-mallory"
        assert request.body["moderation_action"] == "kick"

    asyncio.run(scenario())
```

Here `owner_id="user-boss"` makes the user `boss` the room's owner (their identifier in the test
is `user-boss`).

## Setting up the "server"

What the "server knows" is the fields of `harness.requester`:

| Field | What it sets |
|---|---|
| `room` | the room roster (filled by `harness.join`) |
| `gold` | the gold in the bot's wallet |
| `inventory` | the bot's wardrobe |
| `permissions` | the rights that `privileges` returns |
| `tips_paid` | `False`: tips and purchases answer "not enough gold" |
| `conversation_frames`, `message_frames` | the frames of direct conversations and messages |
| `refuse_with` | any request is refused with a `ResponseError` with this text |

```python
import asyncio

from sukarisebot import Bot, Context, ResponseError, command
from sukarisebot.testing import Harness


class Tipper(Bot):
    @command("tipme")
    async def tipme(self, ctx: Context) -> None:
        if await self.api.tip(ctx.user.id, "gold_bar_10"):
            await ctx.reply("Here you go!")
        else:
            await ctx.reply("Not enough gold.")


def test_a_poor_bot_says_so() -> None:
    async def scenario() -> None:
        harness = Harness(Tipper())
        harness.requester.tips_paid = False
        await harness.start()
        await harness.say("alice", "!tipme")
        assert harness.chats == ["Not enough gold."]

    asyncio.run(scenario())


def test_a_refused_request_raises() -> None:
    async def scenario() -> None:
        harness = Harness(Tipper())
        harness.requester.refuse_with = "That user is not in this room"
        await harness.start()
        try:
            await harness.bot.api.chat("hi")
        except ResponseError as error:
            assert "not in this room" in error.message

    asyncio.run(scenario())
```

## Tips and direct messages

```python
import asyncio

from sukarisebot import Bot, CurrencyItem, Item, MessageEvent, User
from sukarisebot.testing import Harness


class Cashier(Bot):
    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        if self.session is not None and receiver.id == self.session.user_id and isinstance(item, CurrencyItem):
            await self.api.chat(f"+{item.amount}")

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        messages = await self.api.messages(conversation_id)
        if messages:
            await self.api.send_message(conversation_id, messages[0].content.upper())


def test_tips_and_direct_messages() -> None:
    async def scenario() -> None:
        harness = Harness(Cashier(), bot_id="bot-1")
        harness.requester.message_frames = [
            {
                "message_id": "m1",
                "conversation_id": "c1",
                "createdAt": None,
                "content": "hello",
                "sender_id": "user-ann",
                "category": "text",
            }
        ]
        await harness.start()
        ann = User("user-ann", "ann")
        await harness.emit(harness.event_tip(ann, User("bot-1", "bot"), CurrencyItem("gold", 10)))
        await harness.emit(MessageEvent("user-ann", "c1", True))
        assert harness.chats == ["+10"]
        (reply,) = harness.requests("SendMessageRequest")
        assert reply.body["content"] == "HELLO"

    asyncio.run(scenario())
```

## Dialogues with `wait_for`

A command that waits for an answer does not finish until the answer comes. So in a test run it
as a separate task, let it start waiting, feed the answer and wait for the task:

```python
import asyncio

from sukarisebot import Bot, ChatEvent, Context, command
from sukarisebot.testing import Harness


class Asker(Bot):
    @command("ask")
    async def ask(self, ctx: Context) -> None:
        answer = await self.wait_for(
            ChatEvent,
            lambda event: event.whisper and event.user.id == ctx.user.id,
            timeout=5,
        )
        await ctx.reply(f"You answered: {answer.message}")


def test_a_dialog() -> None:
    async def scenario() -> None:
        harness = Harness(Asker())
        await harness.start()
        task = asyncio.create_task(harness.say("alice", "!ask"))
        await asyncio.sleep(0)  # let the command reach wait_for
        await harness.say("alice", "42", whisper=True)
        await task
        assert harness.chats == ["You answered: 42"]

    asyncio.run(scenario())
```

## Timers

Harness **does not run** the `@every` timers: there is no reason to wait for them in a test.
Check the method directly:

```python
import asyncio

from sukarisebot import Bot, every
from sukarisebot.testing import Harness


class Herald(Bot):
    @every(300)
    async def announce(self) -> None:
        await self.api.chat("Room rules: be polite.")


def test_the_announcement() -> None:
    async def scenario() -> None:
        bot = Herald()
        harness = Harness(bot)
        await harness.start()
        await bot.announce()
        assert harness.chats == ["Room rules: be polite."]

    asyncio.run(scenario())
```

## What Harness does not do

- It does not check the **server's rules**: moderator rights, whether the person is in the room,
  the gold limits. Imitate these refusals with the fields `refuse_with` and `tips_paid`.
- It does not filter events by subscriptions: `emit` accepts any event, even if the bot has no
  matching handler (then it simply calls nothing).
- It does not apply rate limits and does not use the network.
- It does not check the protocol. A separate set of the SDK's own tests on a real websocket takes
  care of that (the repository's `tests/` directory, `fake_gateway.py`).

Before running a bot on a real server it is handy to try it once in a test room.
