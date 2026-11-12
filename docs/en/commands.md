**English** | [Русский](../ru/commands.md) | [Português (Brasil)](../pt-BR/commands.md)

# Commands, timers and dialogues

Besides event handlers a bot has three convenient mechanisms: **chat commands** (`!roll`),
**timers** (do something every N seconds) and **dialogues** (ask a question and wait for the
answer). All three are declared right in the bot's class and need no registration.

## Commands: `@command`

```python
import random

from sukarisebot import Bot, Context, command


class Dice(Bot):
    @command("roll", aliases=("dice",), cooldown=(3, 60.0), description="roll a die")
    async def roll(self, ctx: Context) -> None:
        await ctx.reply(f"@{ctx.user.username} rolled {random.randint(1, 6)}")

    @command("shutdown", owner_only=True, description="stop the bot")
    async def shutdown(self, ctx: Context) -> None:
        await ctx.reply("Bye!")
        await self.stop()
```

A player writes `!roll` in the public chat or as a whisper, and the `roll` method runs.

### How the bot understands a command

- The message must **start with the prefix `!`**. Everything after it is split on spaces; the
  first word is the command's name, the rest are arguments.
- The name does not depend on case: `!Roll`, `!ROLL` and `!roll` are one command. However many
  spaces there are between words, the arguments are separated one by one.
- A command is recognised both in the **public chat** and in a **whisper**.
- The bot does not treat its own message as a command.
- If there is no such command, the bot stays silent, and the message itself still goes to
  `on_chat`.
- Commands run **after** the chat event's handler (`on_chat`/`on_whisper`).

### The parameters of `@command`

| Parameter | Description |
|---|---|
| `name` | the command's name: one word without spaces |
| `aliases` | other names of the same command, for example `("dice", "die")` |
| `description` | a short description; `!help` shows it |
| `cooldown` | `(calls, seconds)`: each player is allowed that many calls in any window of this length; over the limit the bot asks them to wait |
| `owner_only` | `True`: only the room's owner runs the command; the bot answers everyone else with a refusal |

Wrong parameters (an empty name, `cooldown=(0, 10)` and so on) raise `InvalidArgument` **when
the class is defined**, not in the middle of the bot's work.

Names and aliases must be unique: a repeated name raises `InvalidArgument` ("the command … is
already registered") when the bot is created.

### `Context`: what a command receives

The only argument of a command method is a `Context`:

| Member | What it is |
|---|---|
| `ctx.user` | who called it (`User`) |
| `ctx.name` | the command's canonical name (even if it was called by an alias), in lower case |
| `ctx.args` | a tuple of the words after the name |
| `ctx.arg(i)` | the `i`-th argument or `None` if there is none |
| `ctx.rest()` | all the arguments as one string |
| `ctx.whisper` | `True` if the command came as a whisper |
| `ctx.text` | the whole original message |
| `ctx.api` | the bot's actions (the same as `self.api`) |
| `await ctx.reply(text)` | reply **to where the command came from**: a whisper to a whisper, the public chat to a line in the chat |

For the message `!say hello all`: `ctx.args == ("hello", "all")`, `ctx.arg(0) == "hello"`,
`ctx.rest() == "hello all"`.

```python
from sukarisebot import Bot, Context, command


class Echo(Bot):
    @command("say", description="repeat the text")
    async def say(self, ctx: Context) -> None:
        text = ctx.rest()
        await ctx.reply(text if text else "Say what? Write: !say text")
```

### Rate limiting (`cooldown`)

`cooldown=(3, 60.0)` means "no more than three calls per 60 seconds per player". It is a sliding
window: a player who exceeds the limit gets the answer "wait N s…", and the counter frees up as
old calls leave the window. The limit works separately for each player and each command. A call
rejected because of `owner_only` does not use up the limit. The bot forgets the records of
players who have not written for a long time by itself, so memory does not grow with every new
player.

### For the owner only: `owner_only`

"Owner" here is the **owner of the room** the bot works in (`bot.owner_id`), not the bot's owner.
It is usually the same person, but not necessarily. You can check the same thing in your own code
with `self.is_owner(user)`.

### The `!help` command

The bot creates `!help` itself and lists all the commands with their descriptions. The commands
are listed in the alphabetical order of the **method names**, and `!help` comes last. To replace
it with your own, declare a command `help`:

```python
from sukarisebot import Bot, Context, command


class Polite(Bot):
    @command("help")
    async def help(self, ctx: Context) -> None:
        await ctx.reply("Write !roll to roll a die.")
```

### What the bot says by itself: `Phrases`

The bot says three phrases on its own behalf: the refusal to a non-owner, the request to wait and
the answer to `!help`. By default they are in Russian. You can replace them by setting the
`phrases` attribute in the bot's class:

```python
from sukarisebot import Bot, Phrases


class English(Bot):
    phrases = Phrases(
        owner_only="@{username}, {prefix}{command} is for the room owner.",
        cooldown="@{username}, wait {seconds} s before {prefix}{command} again.",
        help="Commands: {commands}",
    )
```

| `Phrases` field | When it is used | Template fields |
|---|---|---|
| `owner_only` | a non-owner called an `owner_only` command | `{username}`, `{prefix}`, `{command}` |
| `cooldown` | the command was called too often | `{username}`, `{prefix}`, `{command}`, `{seconds}` |
| `help` | the answer to `!help` | `{commands}`: the list of commands |
| `help_separator` | the separator of commands in the list | — |

The template is formatted with `str.format`: use only the listed fields. An unknown field raises
`KeyError`, which goes to `on_error`.

## Timers: `@every`

```python
from sukarisebot import Bot, every


class Herald(Bot):
    @every(300)
    async def announce(self) -> None:
        await self.api.chat("Do not forget the room rules.")
```

`@every(seconds)` runs the method every `seconds` seconds while the bot is connected.

- The method takes no arguments (apart from `self`).
- The **first run** is `seconds` seconds after connecting, not at once.
- The next run is counted from the *end* of the previous one, so the real period is `seconds`
  plus the time the method takes. Runs of one timer do not overlap.
- An error in a timer does not stop it: it goes to [`on_error`](handlers.md#on_error) (with
  `event=None`).
- While there is no connection, runs are skipped. On reconnection the timers are not restarted;
  they keep going.
- A timer works in a separate task, so it may run while an event handler waits on an `await`.
- `seconds` must be a positive finite number, otherwise `InvalidArgument`.

## Dialogues: `wait_for`

`await self.wait_for(kind, check, timeout=...)` waits for the **next** event of type `kind` that
passes the `check`. Ideal for "asked a question, waiting for the answer":

```python
from sukarisebot import Bot, ChatEvent, Context, command


class Riddle(Bot):
    @command("riddle", cooldown=(1, 60.0), description="a riddle")
    async def riddle(self, ctx: Context) -> None:
        await ctx.reply("What has keys but cannot open locks? Answer by whisper.")
        try:
            answer = await self.wait_for(
                ChatEvent,
                lambda event: event.whisper and event.user.id == ctx.user.id,
                timeout=60,
            )
        except TimeoutError:
            await ctx.reply("Time is up.")
            return
        if answer.message.strip().lower() == "piano":
            await ctx.reply("Correct!")
        else:
            await ctx.reply("Wrong.")
```

| Parameter | Description |
|---|---|
| `kind` | the event's class: `ChatEvent`, `UserJoinedEvent` and so on |
| `check` | a function "does the event fit"; `None`: any event fits |
| `timeout` | how many seconds to wait; when it runs out, `TimeoutError` |

What you need to know:

1. **Always set a `timeout`.** Without it the wait may never end.
2. **While a command waits, the bot does not handle other events.** Handlers go one at a time
   (see [How the SDK works](architecture.md#how-an-event-reaches-a-handler)); a waiting command
   occupies the queue. For a dialogue with one player in a quiet room this is fine; for several
   players at once, start the dialogue as a separate task (below).
3. **`wait_for` sees only events that arrived after the call.** An answer that has already
   arrived and stands in the queue earlier than the command reached `wait_for` is missed: this
   happens when a player writes the answer instantly and the bot is behind. Ask the question
   first, then wait.
4. **The wait fires at the moment the event arrives**, before the queue, so the waiting command
   will see the event it needs even while it occupies the queue itself. After that the event
   goes the usual way into the `on_...` handlers (including `on_whisper`) and into the commands.
5. **The event must reach the bot.** The chat, joins and leaves always arrive. To wait for any
   other event, override its handler (an empty one is enough), otherwise there is no
   subscription to it.
6. If the `check` function raises an exception, it comes out of `wait_for` in your code.

### Dialogues with several players at once

Start the dialogue as a separate task, so that the command finishes at once and the event queue
is not blocked. Do not forget to keep a reference to the task and to pass its errors to
`on_error`:

```python
import asyncio
from collections.abc import Awaitable

from sukarisebot import Bot, ChatEvent, Context, command


class Quiz(Bot):
    def __init__(self) -> None:
        super().__init__()
        self._dialogs: set[asyncio.Task[None]] = set()

    def spawn(self, work: Awaitable[None]) -> None:
        """Start a dialogue in the background: keep the reference, send errors to on_error."""
        task = asyncio.create_task(self._guarded(work))
        self._dialogs.add(task)
        task.add_done_callback(self._dialogs.discard)

    async def _guarded(self, work: Awaitable[None]) -> None:
        try:
            await work
        except Exception as error:
            await self.on_error(error, None)

    @command("quiz", cooldown=(1, 30.0), description="a quiz")
    async def quiz(self, ctx: Context) -> None:
        self.spawn(self._ask(ctx))  # the command finishes at once

    async def _ask(self, ctx: Context) -> None:
        await ctx.api.whisper(ctx.user.id, "What is 6 x 7?")
        try:
            answer = await self.wait_for(
                ChatEvent,
                lambda event: event.whisper and event.user.id == ctx.user.id,
                timeout=60,
            )
        except TimeoutError:
            await ctx.api.whisper(ctx.user.id, "Time is up.")
            return
        verdict = "Correct!" if answer.message.strip() == "42" else "Wrong."
        await ctx.api.whisper(ctx.user.id, verdict)
```

## Data in memory: `state` and `user_state`

- `self.state` is a free dictionary `dict[str, object]` for the bot's data.
- `self.user_state(user_id)` is a personal dictionary per player; it is created on first use.

Both live while the process runs and are **not saved to disk**. For data that must survive a
restart use [`JsonStore`](tools.md#jsonstore-data-between-runs).

```python
from sukarisebot import Bot, Context, command


class Counter(Bot):
    @command("count", description="count my calls")
    async def count(self, ctx: Context) -> None:
        state = self.user_state(ctx.user.id)
        calls = state.get("calls", 0)
        calls = (calls if isinstance(calls, int) else 0) + 1
        state["calls"] = calls
        await ctx.reply(f"@{ctx.user.username}, you have called me {calls} time(s).")
```

## How to test commands

Commands and dialogues are tested without a server through `Harness`; run a dialogue with
`wait_for` as a separate task: see [Testing](testing.md).
