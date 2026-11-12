**English** | [Русский](../ru/tools.md) | [Português (Brasil)](../pt-BR/tools.md)

# Tools

The SDK's helper parts: the room roster, "clean room" mode, the data store, the HTTP client, the
outfit check and starting from the command line.

## The room roster (`bot.room`)

`bot.room` (the `Room` class) answers the question "who is in the room now and where". The
object is **read-only**: the SDK fills it itself.

| Member | What it does |
|---|---|
| `room.users()` | a list of `RoomUser`: everyone who is in the room now |
| `room.get(user_id)` | a person's record by identifier, or `None` |
| `room.find("@Alice")` | a record by name; case and a leading `@` do not matter; `None` if there is none |
| `user_id in room` | whether a person is in the room |
| `len(room)` | how many people are in the room |
| `room.seeded` | `True` if the roster holds everyone in the room, not only those seen arriving |

```python
from sukarisebot import Bot, Context, command


class Finder(Bot):
    @command("where", description="where a player is: !where name")
    async def where(self, ctx: Context) -> None:
        name = ctx.arg(0)
        entry = None if name is None else self.room.find(name)
        if entry is None:
            await ctx.reply("I do not see that player.")
        else:
            await ctx.reply(f"{entry.user.username}: {entry.location}")
```

### What updates the roster

On connecting, the SDK loads the roster from the server (`await bot.refresh_room()` is called by
itself). After that **events** update it. The SDK always receives people joining and leaving
(except in "clean room" mode), so the list of people stays right without any handlers. Movements,
however, reach the bot only if a handler is overridden for them (see
[Event subscriptions](architecture.md#event-subscriptions)): for `bot.room` to know where
everyone stands and sits, override `on_user_move`. The handler's body may be empty:

```python
from sukarisebot import Bot, Location, User


class Tracker(Bot):
    """Keeps the positions in bot.room current and does nothing else."""

    async def on_user_move(self, user: User, position: Location) -> None:
        pass
```

Without `on_user_move` a person's position in the roster is where they were when they entered or
at the last load. You can refresh the roster fully at any moment: `await self.refresh_room()` (one
`info` request). Before version 0.3.0 joins and leaves also updated the roster only if
`on_user_join` and `on_user_leave` were overridden.

## "Clean room" mode

`start(clean_room=True)` (or `run(clean_room=True)`): the bot **makes no request its code did not
ask for**. In particular it does not request the list of people on connecting, so `bot.room`
starts empty (`seeded == False`) and fills from join events. The full list is loaded explicitly:
`await self.refresh_room()`. In this mode the SDK does not subscribe to people joining and leaving
either, until you override their handlers yourself.

The mode is for bots that only listen: they create no extra traffic. For an example see
[`examples/clean_room.py`](../../examples/clean_room.py). From the command line:
`python -m sukarisebot module:Class --clean-room`.

## `JsonStore`: data between runs

`self.state` and `self.user_state()` live only while the process runs. For data that must survive
a restart there is `JsonStore`: a small "key → JSON value" store in one file.

```python
from pathlib import Path

from sukarisebot import Bot, Context, JsonStore, JsonValue, Location, User, command


def add_visit(old: JsonValue, username: str) -> JsonValue:
    record: dict[str, JsonValue] = dict(old) if isinstance(old, dict) else {}
    visits = record.get("visits", 0)
    record["visits"] = (visits if isinstance(visits, int) else 0) + 1
    record["username"] = username
    return record


class VisitCounter(Bot):
    def __init__(self, path: str | Path = "visits.json") -> None:
        super().__init__()  # required: otherwise the commands are not found
        self.store = JsonStore(path)

    async def on_user_join(self, user: User, position: Location) -> None:
        await self.store.update(user.id, lambda old: add_visit(old, user.username))

    @command("visits", description="how many times I have visited")
    async def visits(self, ctx: Context) -> None:
        record = await self.store.get(ctx.user.id)
        count = record.get("visits", 0) if isinstance(record, dict) else 0
        await ctx.reply(f"@{ctx.user.username}, you have visited {count} time(s).")
```

| Method | What it does |
|---|---|
| `await store.get(key, default=None)` | the value by key, or `default` |
| `await store.set(key, value)` | write a value |
| `await store.update(key, change, default=None)` | replace the value with the result of `change(old)` and return the new one |
| `await store.all()` | a copy of all the records (for example, for a leaderboard) |
| `store.path` | the path to the file |

What you need to know:

- **The key is a player's identifier (`user.id`), not the name**: the name can be changed.
- The value is a JSON value: `None`, `bool`, a number, a string, a list or a dictionary. The
  `JsonValue` type describes this for the type checker.
- **A write is atomic**: the data is written to a temporary file that then replaces the old one,
  so a failure in the middle of a write does not leave a half-written file. Disk operations run in
  a worker thread and do not stop the bot.
- **Simultaneous changes are not lost**: `set` and `update` queue up. For "read, change, write"
  use `update`, not a `get` + `set` pair.
- If a write fails (for example, the value cannot be written as JSON), the store stays as it was.
- The file is read whole on first use and kept in memory; each change writes it whole. It suits
  small data, not large databases.
- If the file exists but does not hold a JSON object, the first use raises `ValueError`.

## The HTTP client `bot.http`

For requests to other services (exchange rates, a translator, your database) the bot has a shared
`aiohttp` client, `bot.http`. It is created on first use, closes by itself when the bot stops, and
every request has a 10-second timeout.

```python
from sukarisebot import Bot, Context, command


class Rates(Bot):
    @command("rate", description="a currency rate: !rate USD")
    async def rate(self, ctx: Context) -> None:
        pair = ctx.arg(0) or "USD"
        # The address is made up: put your own service here.
        async with self.http.get("https://example.com/api/rate", params={"pair": pair}) as response:
            await ctx.reply(await response.text())
```

Use it instead of creating a client in every handler.

## The outfit: `outfit_problems` and `category_of`

`api.wear(items)` first checks the outfit on the SDK's side, so that you get a clear
`InvalidArgument` instead of a server refusal. You can call the same check yourself:

```python
from sukarisebot import Item, outfit_problems

items = [Item(type="clothing", amount=1, id="shirt-n_plaid_blackwhite")]
for problem in outfit_problems(items):
    print(problem)
```

`outfit_problems(items)` returns a list of problems (empty: the outfit is fine). It checks that:

- all the items are clothing (`type == "clothing"`);
- no item repeats;
- each **basic category** (`shirt`, `pants`, `skirt`, `dress`, `fullsuit` and the body parts)
  occurs at most once;
- all the body parts are present: `body-flesh`, `eye`, `eyebrow`, `nose`, `mouth`;
- the body is covered: a shirt and pants, a shirt and a skirt, a dress or a fullsuit.

`category_of(item_id)` determines the basic category from an item's identifier (it starts with
the category's name) or returns `None` for accessories.

The SDK reads the category from the identifier, while the server reads it from the item's type in
the catalog. So items with identifiers `bag-…`, under which anything can be (an eyebrow, a shirt,
pants), are not classified by the SDK, and it does not count as a mistake what they are able to
make up for: the last two points of the list above are checked only if there are not enough such
items to cover what is missing. Earlier such outfits, for example ones copied from a person with
`outfit_of`, were refused wrongly.

The SDK does not check ownership of items: only the server knows it. While the bot's owner has an
active PREMIUM, changing the outfit is free: the bot can put on any item of the catalog. The bot
can find out its own current outfit with `await bot.my_outfit()`.

## Starting from the command line

You can start a bot without a launch script of your own, like the official `highrise` command:

```bash
python -m sukarisebot examples.dice:Dice --room room-... --token srbot_...
sukarisebot examples.dice:Dice --clean-room
```

| Parameter | Description |
|---|---|
| `module:Class` | the bot as "module name, colon, class name"; the module is searched for in the current directory and by an ordinary `import` |
| `--room ID` | the room's identifier (or the `SUKARISEBOT_ROOM_ID` variable) |
| `--token TOKEN` | the bot's token (or the `SUKARISEBOT_TOKEN` variable) |
| `--url URL` | the gateway address (or the `SUKARISEBOT_URL` variable) |
| `--clean-room` | "clean room" mode |
| `--log-level LEVEL` | `DEBUG`, `INFO` (the default), `WARNING` or `ERROR`; any other value is a usage error |

Exit code: `0`: normal, `1`: the server refused (`ConnectionRefused` and others), `2`: the bot was
not found (the module cannot be imported or the class does not inherit `Bot`). The bot is created
by a constructor **without arguments**.

The same lookup is available from code: `load_bot("module:Class")` returns a ready bot.

## Low-level parts

For non-standard tasks the package also exports its internal classes:

- `Engine`: the connection: websocket, event queue, reconnection. It is created by `Bot` itself;
  you need it if you want to manage the connection by hand.
- `Requester`: the interface "send a request, get an answer". `Engine` and the testing
  `RecordingRequester` implement it. `BotAPI` depends only on it.
- `Commands`, `Command`, `CommandSpec`, `CommandHandler`: the command registry and its parts.

An ordinary bot does not need them. How they work is in [How the SDK works](architecture.md) and
[Protocol](protocol.md).
