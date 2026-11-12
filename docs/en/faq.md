**English** | [Русский](../ru/faq.md) | [Português (Brasil)](../pt-BR/faq.md)

# FAQ

## The bot connected but does not react to messages

Check in this order:

1. **Is there a handler or a command.** The bot hears only what has an overridden handler
   (`on_chat`, `on_user_join` …) or a declared command. See [Handlers](handlers.md).
2. **Commands start with `!`.** `!roll` is a command, `roll` is not.
3. **An owner-only command** (`owner_only=True`) answers everyone except the *room's* owner
   with a refusal.
4. **The bot is really in the room.** It should appear in the list of people under the name you
   gave it. If not, turn on the log (`logging.basicConfig(level=logging.INFO)`) and look for the
   cause in the [table of refusals](errors.md#refusals-when-connecting).
5. **An error in your code.** Exceptions do not bring the bot down; they go to `on_error` and to
   the `sukarisebot` log: turn the log on to see them.

## `bot.room` shows people in the wrong place

The roster always sees people joining and leaving (except in "clean room" mode), so people who
left disappear from it and new ones appear by themselves. Movements, however, arrive only if
`on_user_move` is overridden (its body may be empty): without it a person's position in the
roster is where they were on entering. More in [Tools](tools.md#the-room-roster-botroom). You can
refresh the roster fully by calling `await self.refresh_room()`. If people who left still stay in
the list, check whether "clean room" mode is on and whether you use an SDK older than 0.3.0:
there, joins and leaves were taken into account only if `on_user_join` and `on_user_leave` were
overridden.

## `wait_for` waits until the timeout and gets nothing

- The event you need must reach the bot. The chat, joins and leaves always arrive, and for any
  other event override its handler (an empty one is enough).
- The `check` must return `True` for the event you need; check the condition.
- Always set a `timeout`. See [Dialogues](commands.md#dialogues-wait_for).

## The bot "freezes" while it waits for a player's answer

Handlers run one at a time, and a waiting command occupies the queue. This is deliberate (that
way no locks are needed in the code). For dialogues with several players at once, start the
dialogue as a separate task: the recipe is in
[Dialogues with several players at once](commands.md#dialogues-with-several-players-at-once).

## Can I use `requests`, `time.sleep` and other blocking calls?

No. A blocking call stops the whole event loop and the bot stops reading the socket. Use
`await asyncio.sleep(...)`, `bot.http` (aiohttp) or `await asyncio.to_thread(function)` for heavy
synchronous work.

## How many bots can I create and keep in a room?

Up to **three active bots per account** and up to **three bots at the same time in one room**.
There is also a general limit on keys issued per account (the cabinet tells you if it is
exhausted). To create and run a bot, the owner must have an active PREMIUM subscription.

## What happens if PREMIUM ends?

The key is not deleted. The bot cannot connect until the subscription is renewed, and a bot that
is already connected gets a temporary refusal at its next connection. The SDK keeps retrying by
itself, so after renewal the bot comes back without your involvement.

## How do I get the gold the bot has earned?

The bot receives tips as gold into its wallet (`await self.api.gold()`). The owner collects the
accumulated gold in the personal cabinet: on the bot's card there is a **"Withdraw gold"** button.
The bot can also spend its gold itself: `api.tip(...)` and `api.buy_item(...)`.

## Why does the bot not write first in direct messages?

It is by design: the bot **replies** in conversations it is already in, and the person starts the
conversation. `send_bulk_message` also writes only to people who have already written to the bot.

## Does the bot work in 3D rooms?

Almost everything. In 3D these work: chat, whispers, walking, emotes, reactions, sitting on
furniture, teleport, moderation, tips (giving), the list of people, direct messages, the wallet,
the wardrobe and the outfit. The bot receives people's walks and emotes. People's reactions are
not sent by the 3D client, so the bot does not receive them there. The bot receives people's tips
in 3D as well. A summary is in the [Actions reference](api.md#summary). If the server does not
support 3D for bots, the connection is refused with a clear text.

## Can I run several bots in one process?

Yes: each `Bot` object has its own engine and its own connection.

```python
import asyncio

from sukarisebot import Bot


class First(Bot):
    pass


class Second(Bot):
    pass


async def main() -> None:
    await asyncio.gather(
        First().run(token="srbot_1...", room_id="room-1..."),
        Second().run(token="srbot_2...", room_id="room-2..."),
    )


asyncio.run(main())
```

If one of the bots ends with an error, `gather` re-raises it; for the others to keep working,
wrap each start in its own `try/except` or use `return_exceptions=True`.

## How do I keep a bot running on a server?

Run the script as a system service, so that it starts after a reboot and restarts after a
failure. An example for Linux (`/etc/systemd/system/sukarisebot.service`):

```ini
[Unit]
Description=SukaRise bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/mybot
EnvironmentFile=/etc/mybot.env
ExecStart=/opt/mybot/.venv/bin/python -m sukarisebot mybot:MyBot
Restart=on-failure
RestartSec=5
User=mybot

[Install]
WantedBy=multi-user.target
```

`/etc/mybot.env` holds `SUKARISEBOT_TOKEN=…` and `SUKARISEBOT_ROOM_ID=…`; the file's permissions
should be for the service's user only. The SDK reconnects by itself after connection breaks, and
`Restart=on-failure` restarts the process after an unexpected exit.

## What does the bot do when the server restarts or the connection is lost?

The bot connects again by itself as long as `Bot.run()` was called with `reconnect=True` (the
default). The pauses grow from 0.5 s to 30 s with a random spread. After every new connection
`on_start` is called, so the greeting and the subscriptions are sent again. A server that is
silent for longer than three keepalive intervals (about a minute) is considered gone: the bot
closes the connection and connects again. The final refusals after which the bot does not retry:
a wrong token (401, 403), a wrong request (400) and a connection from another place. The bot
retries an HTTP 404 answer, because the route may be unavailable while the server is being
updated, but for no more than 5 minutes in a row: if the gateway answers 404 for all that time,
the bot finishes with `ConnectionRefused` and asks you to check the address.

## How do I replace the token?

In the cabinet press **"New token"** on the bot's card: the old token stops working at once. Put
in the new one and restart the bot. A running bot with the old token gets the refusal "invalid or
revoked bot token" at its next connection.

## Why do I see the refusal "Rate limit exceeded"?

The server limits how often requests may be sent, per category, and the SDK usually waits its turn
by itself. If the server still refused (network delays made the counters drift apart), the SDK
repeats the request up to three times and then raises `RateLimited`. If you see it often, call the
methods of one category less often (for example, `chat` allows 20 per 10 seconds) or combine
lines. See [Errors and refusals](errors.md#rate-limit).

## Why are the server's refusal texts in English?

The protocol is compatible with the official Highrise SDK, and the gateway sends refusal texts in
English. Translations of the typical refusals are in
[Errors and refusals](errors.md#refusals-of-individual-requests-responseerror). The texts of the
SDK's own exceptions and the bot's default phrases are in Russian; the bot's phrases can be
replaced with [`Phrases`](commands.md#what-the-bot-says-by-itself-phrases).

## How do I stop the bot?

From the console: `Ctrl+C`. From code: `await self.stop()` (for example, in a command for the
owner); `run()`/`start()` return after that.

## Where can I see what the bot sent and received?

A running bot does not write every request and event to the log, so as not to clutter it. `DEBUG`
shows only the skipped frames of unknown kinds. To see all the bot's requests, run it in
[`Harness`](testing.md): it records every action in `harness.requester.sent`. For a live
connection add logging to your own handlers.
