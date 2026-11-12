**English** | [Русский](../ru/errors.md) | [Português (Brasil)](../pt-BR/errors.md)

# Errors and refusals

This page lists all the SDK's exceptions, what they mean and what to do about them, plus a
table of the refusals the server sends: when connecting and for individual requests.

> **Language of the messages.** The texts of the SDK's exceptions are in Russian. The texts of
> the refusals the server sends (`error.message`) are in English, as in the official protocol.
> Below, each of them comes with an explanation and advice.

## Exception hierarchy

All SDK errors inherit `SukaRiseError`, so `except SukaRiseError` catches them all.

```text
SukaRiseError
├── ConnectionRefused
├── ResponseError
│   └── RateLimited
├── RequestTimeout
├── NotConnected
├── ProtocolError
└── InvalidArgument (also a ValueError)
```

| Exception | Attributes | When it is raised | What to do |
|---|---|---|---|
| `InvalidArgument` | — | empty text, an unknown reaction/gold bar/action, a coordinate outside ±1000, a seat number outside 0…255, an identifier or tag that is too long, an outfit that breaks the rules, a wrong command name. **The request was not sent.** | Fix the call in your code. It is a programmer's error, not a connection failure. |
| `ResponseError` | `message` | The server refused a request: no rights, the person is not in the room, the server does not support the action. The connection keeps working. | Read `error.message` and, if needed, answer the player. See the table below. |
| `RateLimited` | `message` | The server refused because of the rate limit, and several retries by the SDK did not help. The request **did not run**. Inherits `ResponseError`. | Send requests less often; try again later. More in the "Rate limit" section below. |
| `RequestTimeout` | — | The server did not answer within 10 seconds. The request may have been carried out. | If the action must not be repeated blindly (a tip, a purchase), check the result first (`await api.gold()`). |
| `NotConnected` | — | `bot.api` used outside a running bot; a request during reconnection; a break in the middle of a request. | Wait for the connection; in timers check `self.connected`. |
| `ConnectionRefused` | `message`, `do_not_reconnect` | The server did not accept the connection or ended the session. It comes out of `run`/`start`. | See the "Refusals when connecting" table below. |
| `ProtocolError` | — | The server sent a frame the SDK does not understand. The SDK skips a single such frame and logs it. | Usually nothing: report the problem if it repeats. |

## How to handle them

```python
from sukarisebot import Bot, Context, InvalidArgument, NotConnected, RequestTimeout, ResponseError, command


class Careful(Bot):
    @command("kick", owner_only=True, description="kick someone: !kick name")
    async def kick(self, ctx: Context) -> None:
        name = ctx.arg(0)
        if name is None:
            await ctx.reply("Give a name: !kick name")
            return
        target = self.room.find(name)
        if target is None:
            await ctx.reply(f"{name} is not in the room.")
            return
        try:
            await self.api.kick(target.user.id)
        except ResponseError as error:
            await ctx.reply(f"The server refused: {error.message}")
        except (NotConnected, RequestTimeout):
            await ctx.reply("The connection to the room is unstable, try again later.")
        except InvalidArgument as error:
            await ctx.reply(f"Invalid command: {error}")
```

If an exception is not caught, it does not bring the bot down: the SDK passes it to
[`on_error`](handlers.md#on_error) and the bot keeps working.

## Rate limit

The server limits how often requests may be sent, per category, and the SDK keeps the same
counters, so it almost always waits its turn by itself. But network delays can squeeze the gaps
between requests, and the server may decide a fraction of a second before the SDK that the
budget is spent. It then answers `Rate limit exceeded for <category> requests` **before** the
request is carried out. Earlier, such a refusal became a `ResponseError` at once. Now the SDK
repeats the request up to three times with a pause of one second (this is safe: the request did
not run) and only then raises `RateLimited`. The exception inherits `ResponseError`, so an
existing `except ResponseError` keeps working.

## Refusals when connecting

The `ConnectionRefused` exception comes out of `run()`/`start()` when the bot has stopped and
cannot go on. The "SDK" column says what the SDK does:

- **retries**: the server's word is "the refusal is temporary" (`do_not_reconnect = False`): a
  bot with `reconnect=True` does not finish but tries again with a growing pause of up to 30
  seconds;
- **finishes**: the refusal is final (`do_not_reconnect = True`): `run()` raises
  `ConnectionRefused`.

With `reconnect=False` the exception is raised in both cases, including a temporary HTTP refusal
(for example 503); you can tell them apart by `error.do_not_reconnect`.

| Server text | What it means | What to do | SDK |
|---|---|---|---|
| `invalid or revoked bot token` | The token is wrong, was replaced with the "New token" button, the bot is switched off or deleted, or the owner is blocked. | Check the token; if needed, issue a new one in the cabinet. | finishes |
| `the bot's owner needs an active PREMIUM subscription` | The bot's owner has no active PREMIUM subscription. | Renew PREMIUM; the bot will connect by itself. | retries |
| `the bot needs designer rights in the room: add the bot's username as a designer in the room settings` | The bot is not a designer of the room. | Add the bot's login to the room's designers. | finishes |
| `the room does not exist` | There is no room with this ID. | Check `room_id`. | finishes |
| `the room is full` | There is no space in the room. | Free a place or choose another room. | finishes |
| `the room already holds the maximum number of bots` | The room already has three bots. | Disconnect one of the bots. | finishes |
| `bots cannot join this 3D room: the 3D world service is not available to bots on this server` | This 3D room is not available to bots on the server. | Use a 2D room. | finishes |
| `bots are not enabled on this server` | The bot API is switched off on the server. | Contact the server's administrator. | finishes |
| `A valid room-id header is required` | `room_id` is empty or has characters that are not allowed. | Check `room_id`. | finishes |
| `This bot connected from another place` | The same token was connected elsewhere; the new connection wins. | Run one bot per token. | finishes |
| `the room is not ready, try again shortly` | The room is not ready yet (for example, a 3D world is starting). | Nothing: the SDK will retry. | retries |
| `The room could not be joined right now` | A temporary error on entry. | Nothing: the SDK will retry. | retries |
| `Authentication is temporarily unavailable` | A temporary error while checking the token. | Nothing: the SDK will retry. | retries |
| `The server is restarting` | The server is restarting. | Nothing: the SDK will retry. | retries |
| HTTP 404 | There is no such address: a wrong `SUKARISEBOT_URL`, or the bot API is not connected to the web server. While the server is being updated the route can disappear for a moment, so the SDK keeps trying, but for no more than 5 minutes in a row. | Check the address. | retries, then finishes |
| HTTP 400, 401, 403 | The request was rejected at the HTTP level. | Check the address and the token. | finishes |
| HTTP 503 `too many bot connections` | The gateway is overloaded with connections. | Nothing: the SDK will retry. | retries |

The SDK also reconnects after a network break and after any other temporary HTTP answer.

## Refusals of individual requests (`ResponseError`)

Typical texts a bot may see in `error.message`:

| Server text | What it means and what to do |
|---|---|
| `Rate limit exceeded for <category> requests` | The rate limit was exceeded. The SDK waits its turn and retries such a refusal by itself; it comes out as `RateLimited`. |
| `The message is empty` / `The message is longer than 500 characters` | An empty or too long line (the SDK splits long ones itself). |
| `That user is not in this room` / `That user does not exist` | The addressee of a whisper, reaction or tip is not in the room. |
| `The bot is muted in this room` / `The bot is banned from this room` | The bot was muted or banned. |
| `The bot cannot whisper this user` / `The whisper could not be sent` / `This user is not accepting whispers from the bot` | The whisper was not delivered. |
| `The bot cannot walk there` / `The destination is not on the floor of this room` / `The destination is not a point in the room` | The point for `move_to` or `teleport_user` is not reachable. |
| `That seat is not in this room` | There is no such seat for `sit_on`. |
| `Teleporting a user needs moderator rights in the room` | Teleporting needs moderator rights. |
| `That seat is taken` | The seat is taken by a person or another bot. Choose another one. |
| `The bot is already sitting` | The bot is already sitting. Stand up first by walking somewhere (`move_to`). |
| `The bot could not reach that seat` | In a 3D world the bot did not reach the seat within 8 seconds and stayed standing. Choose another seat or a point closer to it. |
| `The bot sat on another seat, and that one is not reachable` | In a 3D world the world seated the bot on another seat, and the chosen one is unreachable. The bot is now sitting on a different seat. |
| `That user was moved a moment ago` | In a 3D world a person can be moved no more often than once per 0.6 s. Repeat after a second. |
| `The bot is not in this room` / `The bot is no longer in the room` | The bot has not entered the room yet or has already left it. Wait for it to enter. |
| `The emote is unknown` / `The bot cannot perform that emote` | There is no such emote, or the bot cannot play it (a paid one, without PREMIUM on the owner). |
| `This emote needs a partner, and a bot cannot give one yet` | Paired emotes are not available to bots. |
| `Unknown reaction` | An unknown reaction. |
| `That gold bar is not available` / `That user cannot be tipped` / `The recipient cannot hold more` / `Tips are unavailable right now` | The tip was not sent. Not having enough gold is not a refusal: `tip` returns `False`. |
| `That item does not exist` / `That item is not sold to bots` / `That item is not available right now` / `That item is only for players with SukaRise PREMIUM` / `Bots can buy only items sold for gold` / `The bot cannot hold more items` / `The shop is unavailable right now` | The purchase is impossible. Not having enough gold is not a refusal: `buy_item` returns `False`. |
| `The bot's owner needs an active PREMIUM subscription to change the bot's outfit` | Changing the outfit is forbidden without PREMIUM on the owner. |
| `Unknown item: …` / `The outfit is empty` / `The outfit has too many items` / `The outfit has an item without an id` / `The outfit is missing a … item` / `The outfit wears two … items; a bot wears one of each basic part` / `The outfit does not cover the body…` | The outfit did not pass the server's check. |
| `Bots cannot change room privileges; the room owner does that` / `Changing room privileges from bots is not available yet` | `set_privileges` always refuses: only the owner and the staff change rights in a room. |
| `The conversation does not exist` / `Bots take part in direct conversations only` / `The bot cannot write to this conversation` | There is no such conversation, it is not a direct one, or the bot cannot write to it. |
| `The bot has no open conversation with these users: bots answer people who wrote first` | `send_bulk_message`: the bot writes only to people who have already written to it. |
| `This request is not supported on this server` | The server does not support this operation. |
| `Internal error` | An internal server error. |

Some actions **always** refuse bots on SukaRise: `set_privileges`, voice chat, the backpack, paid
room services, moving people to another room, media messages. The SDK has no methods for them,
except `set_privileges`.

## Log

The SDK writes to a logger named `sukarisebot`. To see reconnections, refusals and errors in
handlers, turn the output on:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
```

Levels: `INFO`: reconnections; `WARNING`: a lost connection, temporary refusals, dropped frames
and events; `ERROR`: exceptions in your code (with a traceback). The token never gets into the
log.
