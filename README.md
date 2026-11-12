**English** | [Русский](README.ru.md) | [Português (Brasil)](README.pt-BR.md)

# SukaRiseBot

An asynchronous, fully typed **Python SDK for SukaRise bots**. A bot joins a room over a
websocket, reads the chat and the room's events, walks, talks, moderates, receives tips,
answers direct messages and runs its own small economy with a wallet. All of it is plain
Python with editor hints and strict types.

```python
import random

from sukarisebot import Bot, Context, Location, User, command


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Welcome, {user.username}!")

    @command("roll", cooldown=(3, 60.0), description="roll a die")
    async def roll(self, ctx: Context) -> None:
        await ctx.reply(f"@{ctx.user.username} rolled {random.randint(1, 6)}")


if __name__ == "__main__":
    Greeter().start()
```

## Features

- **Chat and talking:** public lines, whispers, a hidden channel between bots.
- **Movement:** walking, sitting on furniture, teleporting players (with moderator rights).
- **Moderation:** `kick`, `ban`, `unban`, `mute`, reading rights in the room.
- **Tips:** the bot receives tips in gold into its own wallet and its owner collects them in
  the personal cabinet; the bot can also tip people and buy items with its own gold.
- **Direct messages:** the bot receives and handles direct messages and replies to them.
- **Appearance:** the bot changes its outfit and can put on its owner's outfit on the `myoutfit` command.
- **Commands, timers and dialogues:** `@command`, `@every`, `wait_for`.
- **Data between runs:** `JsonStore` with atomic writes.
- **Tests without a server:** `Harness` checks a bot in memory.
- **Strict types and hints:** `py.typed`, a description for every public name, `mypy --strict`
  and `pyright` in `strict` mode.

## Requirements

- Python **3.13** or newer;
- a SukaRise account with an active **PREMIUM** subscription (the bot's owner);
- the `aiohttp` dependency is installed automatically.

## Installation

The repository is public: you need neither a GitHub account nor `gh`. The package is not on
PyPI yet, so install it from the repository:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install "sukarisebot @ git+https://github.com/fluxuscode/sukarise-bot-sdk.git"
```

To get a specific version, append `@v0.2.0` (a tag name) to the address, or download a `.whl`
file from the [Releases](https://github.com/fluxuscode/sukarise-bot-sdk/releases) page and
install it with `pip install file-name.whl`.

## Quick start

1. In the SukaRise personal cabinet open the **"Bots"** section, create a bot and save its
   token (`srbot_…`): it is shown only once.
2. In your room's settings find the bot by name and add it as a **designer** (and as a
   **moderator** if the bot is going to moderate).
3. Start the bot, passing the token and the room ID:

   ```bash
   export SUKARISEBOT_TOKEN="srbot_..."
   export SUKARISEBOT_ROOM_ID="room-..."
   python examples/greeter.py
   ```

Step by step, with a troubleshooting table, it is in the **[Quick start](docs/en/quickstart.md)**.

## Documentation

The documentation comes in three languages: [English](docs/en/README.md),
[Русский](docs/ru/README.md), [Português (Brasil)](docs/pt-BR/README.md). The pages of the
English version are listed below.

| Page | What it covers |
|---|---|
| [Quick start](docs/en/quickstart.md) | Installation, token, rights, first run |
| [How the SDK works](docs/en/architecture.md) | How everything works inside |
| [Event handlers](docs/en/handlers.md) | All the `on_...` methods |
| [`BotAPI` reference](docs/en/api.md) | All the bot's actions |
| [Commands, timers and dialogues](docs/en/commands.md) | `@command`, `@every`, `wait_for` |
| [Data models](docs/en/models.md) | `User`, `Position`, events and more |
| [Errors and refusals](docs/en/errors.md) | Exceptions and server refusals |
| [Testing](docs/en/testing.md) | `Harness` |
| [Tools](docs/en/tools.md) | Room roster, `JsonStore`, `bot.http`, CLI |
| [Recipes](docs/en/recipes.md) | Ready-made solutions |
| [Protocol](docs/en/protocol.md) | Frames at the network level |
| [Editors and hints](docs/en/editors.md) | PyCharm, VS Code, mypy, pyright |
| [FAQ](docs/en/faq.md) | Troubleshooting |

Ready-made example bots are in the [`examples/`](examples/) directory: a greeter, a dice
bot with commands, a quiz that waits for answers, a "clean room" bot, a thank-you for tips,
a visit log and a tip-collecting bot. The history of changes is in [CHANGELOG.md](CHANGELOG.md).

## What works and what does not

| Capability | 2D rooms | 3D rooms |
|---|---|---|
| Chat, whispers, channel between bots | yes | yes |
| People joining and leaving | yes | yes |
| Events for people's movement, emotes and reactions | yes | people's walks and emotes; the 3D client does not send people's reactions |
| Walking (`move_to`) | yes | yes |
| Emotes | yes | yes |
| Reactions, sitting on furniture | yes | yes |
| Teleport and moderation (moderator rights needed) | yes | yes |
| Tips (receiving and giving) | yes | yes |
| Direct messages | yes | yes |
| Wallet, wardrobe, outfit, purchases for gold | yes | yes |

Not available to bots on the SukaRise server: paired emotes, changing rights in a room
(`set_privileges` always refuses), voice chat, the backpack, paid room services, moving people
to another room, media messages.

## Language of the texts in the SDK

The descriptions in the code (docstrings), the texts of the SDK's exceptions and the bot's
default phrases (the refusal to a non-owner, "please wait", `!help`) are in Russian. The bot's
phrases are replaced in one line: `Bot.phrases = Phrases(...)` (see
[Commands, timers and dialogues](docs/en/commands.md)). Refusal texts from the server arrive in
English and are passed on as they are.

## Origin of the code

The `sukarisebot` SDK was made on the clean-room design principle. It was written independently
for the SukaRise protocol and is not affiliated with Pocket Worlds or its Highrise project: it is
not their product and is not endorsed by them. The field names and the frame format match the
official Highrise Python SDK, which is done so that code can be ported.

## Development

```bash
pip install -e ".[test]"
python -m pytest        # tests run against a real websocket stand-in gateway (tests/fake_gateway.py)
python -m ruff check .  # linter
python -m mypy          # strict type check
python -m pyright       # strict type check
```

The tests also run the programs in `examples/` and the pieces of code from the documentation,
so the documentation does not drift away from the code. They also keep the three languages of
the documentation the same in structure: pages, headings, tables, links and code blocks.
