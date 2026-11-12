**English** | [Русский](../ru/quickstart.md) | [Português (Brasil)](../pt-BR/quickstart.md)

# Quick start

In ten minutes you will create a bot in the personal cabinet, give it rights in a room and run
your first script. If something goes wrong, look at [Errors and refusals](errors.md) and the
[FAQ](faq.md).

## What you need

| What | Why |
|---|---|
| A SukaRise account with an active **PREMIUM** subscription | Bots are a PREMIUM feature. Without a subscription a bot key cannot be created, and an existing key stops connecting (it works again after renewal). |
| A room where you can add designers and moderators | A bot enters a room only on the owner's invitation. |
| Python **3.13** or newer | The SDK uses features of recent versions of the language. |

## Step 1. Install the SDK

Create and activate a virtual environment:

```bash
python -m venv .venv
# Linux and macOS
source .venv/bin/activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
```

Install the package from the repository (it is public, so no GitHub account is needed):

```bash
pip install "sukarisebot @ git+https://github.com/fluxuscode/sukarise-bot-sdk.git"
```

To get a specific version, append `@v0.2.0` (a tag name) to the address, or download a `.whl`
file from the [Releases](https://github.com/fluxuscode/sukarise-bot-sdk/releases) page and
install it with `pip install file-name.whl`. The package is not on PyPI yet.

The only dependency is `aiohttp`; it is installed automatically. To check:

```bash
python -c "import sukarisebot; print(sukarisebot.__version__)"
```

## Step 2. Create a bot in the personal cabinet

1. Open the SukaRise personal cabinet and go to the **"Bots"** section.
2. Type the bot's name in the **"Bot name"** field and press **"Create bot"**. The name is the
   bot's login in the game and is checked like a player's nickname: 3 to 32 characters, Latin
   letters, digits and `_ . -`, and it must not be taken.
3. The cabinet shows the **token** (a string like `srbot_…`) and offers to copy it. Save the
   token right away: **it will not be shown again**. If you lose it, press **"New token"**:
   the old one stops working.
4. The bot's row shows the **"room login"**: the name you chose. You need it for the
   next step.

A new bot immediately looks like a finished character: it gets an appearance based on the
owner's gender (female or male, and male if the profile gives no gender), a background and a
profile pose. You can change the bot's clothes later from code.

One account can have up to three bots. The **"Disable"**/**"Enable"** buttons stop and resume
a key, **"Delete"** removes the bot for good.

> **The token is the bot's password.** Do not publish it in a repository, in chats or in
> screenshots. Keep it in an environment variable or in a file that does not get into git. If
> the token leaks, issue a new one.

## Step 3. Give the bot rights in the room

A bot is a participant of the room just like a person and obeys the same rules.

1. Open your room's settings.
2. Find the bot by name and add it as a **designer** of the room. Your own bots are shown first
   in the recommendations. Without this the bot will not get in: the server answers that the
   bot needs designer rights.
3. If the bot is to **moderate** (`kick`, `ban`, `mute`) or **teleport** people, add it as a
   **moderator** too. The "designer" right is not enough for that.

A room can hold up to three bots at the same time.

## Step 4. Find the room ID

A bot connects to a room by its identifier: a string like `room-ee3c8c43fb41e0b0`. You pass it as
`room_id` when starting.

## Step 5. Write and run the bot

Create a file `greeter.py`:

```python
from sukarisebot import Bot, Location, User


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Welcome, {user.username}!")


if __name__ == "__main__":
    Greeter().start()
```

It is convenient to pass the token and the room through environment variables, so that they do
not end up in the code.

Linux and macOS:

```bash
export SUKARISEBOT_TOKEN="srbot_..."
export SUKARISEBOT_ROOM_ID="room-..."
python greeter.py
```

Windows, PowerShell:

```powershell
$env:SUKARISEBOT_TOKEN = "srbot_..."
$env:SUKARISEBOT_ROOM_ID = "room-..."
python greeter.py
```

Windows, cmd:

```bat
set SUKARISEBOT_TOKEN=srbot_...
set SUKARISEBOT_ROOM_ID=room-...
python greeter.py
```

If you need a gateway address other than the default one, set `SUKARISEBOT_URL` (for example,
for a test server). The token, the room and the address can also be passed as arguments:
`Greeter().start(token="…", room_id="…", url="…")`.

The bot appears in the room as a player with the bot flag, under the name you gave it, and
greets everyone who enters. You can stop it with `Ctrl+C`.

You can also run a bot without a launch script of your own, with a command:

```bash
python -m sukarisebot greeter:Greeter --room room-... --token srbot_...
```

(`greeter:Greeter` is "module:Class"; the module is searched for in the current directory. The
command `sukarisebot greeter:Greeter` does the same.)

## What next

- Teach the bot commands and timers: [Commands, timers and dialogues](commands.md).
- See all the events a bot can listen to: [Event handlers](handlers.md).
- Find out what a bot can do: [`BotAPI` reference](api.md).
- Ready-made solutions for typical tasks: [Recipes](recipes.md).
- Understand how it all works inside: [How the SDK works](architecture.md).

## If the bot does not connect

The most common causes:

| What you see | What to do |
|---|---|
| `ConnectionRefused: invalid or revoked bot token` | The token is wrong, was replaced with the "New token" button, or the bot is switched off or deleted. Check the token. |
| `ConnectionRefused: the bot needs designer rights in the room…` | Add the bot's login to the room's designers (step 3). |
| The bot does not enter the room, and the console repeats warnings with the text `the bot's owner needs an active PREMIUM subscription` | The owner's PREMIUM has ended. The refusal is temporary: the bot keeps trying by itself and connects once the subscription is renewed. |
| `ConnectionRefused` mentioning `HTTP 404` | A wrong gateway address, or the bot API is not enabled on the server. The bot keeps retrying for 5 minutes in a row and then finishes. Check `SUKARISEBOT_URL`. |

The full table of server refusals is in [Errors and refusals](errors.md). To see what is going
on inside, turn on the log:

```python
import logging

logging.basicConfig(level=logging.INFO)
```
