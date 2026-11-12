**English** | [Русский](../ru/README.md) | [Português (Brasil)](../pt-BR/README.md)

# SukaRiseBot documentation

SukaRiseBot is an asynchronous, fully typed Python SDK for SukaRise bots. This documentation
is written for people who want not only to run a bot but also to understand how it all works.

## Where to start

If you are here for the first time, read in this order:

1. **[Quick start](quickstart.md)**: create a bot in the personal cabinet, give it rights in
   a room and run your first script.
2. **[Event handlers](handlers.md)**: what a bot can listen to: chat, joins, tips, direct
   messages and more.
3. **[`BotAPI` reference](api.md)**: what a bot can do: talk, walk, moderate, give tips,
   reply to direct messages.
4. **[Commands, timers and dialogues](commands.md)**: `!commands`, periodic tasks and
   questions that wait for an answer.

## All pages

| Page | What it covers |
|---|---|
| [Quick start](quickstart.md) | Installation, token, rights in the room, first run |
| [How the SDK works](architecture.md) | How the SDK is built inside: layers, life cycle, event order, limits, reconnection |
| [Event handlers](handlers.md) | All the `on_...` methods: when they are called and what they receive |
| [`BotAPI` reference](api.md) | All of the bot's actions: parameters, limits, exceptions |
| [Commands, timers and dialogues](commands.md) | `@command`, `@every`, `wait_for`, `Phrases`, the bot's state |
| [Data models](models.md) | `User`, `Position`, `Item`, events and other immutable classes |
| [Errors and refusals](errors.md) | The SDK's exceptions and a table of server refusals with translations and advice |
| [Testing without a server](testing.md) | `Harness`: checking a bot without connecting |
| [Tools](tools.md) | The room roster, "clean room", `JsonStore`, `bot.http`, the outfit, the command line |
| [Recipes](recipes.md) | Ready-made solutions to typical tasks |
| [Protocol](protocol.md) | Frames, requests and events at the network level |
| [Editors and hints](editors.md) | PyCharm, VS Code, mypy and pyright: how to turn on hints and strict types |
| [FAQ](faq.md) | Solutions to typical problems |

## Principles of the SDK

- **Strict typing.** All public functions and data are typed; the SDK passes `mypy --strict`
  and `pyright` in `strict` mode. The data you receive is immutable.
- **Errors where you made them.** Arguments are checked before sending: a wrong call raises
  `InvalidArgument` on your line of code, not a server refusal later.
- **A bot obeys the same rules as a person.** A bot has no back door: moderator rights, limits
  and room rules are the same.
- **Your code does not break the bot.** An exception in a handler, a command or a timer does
  not stop the bot: it goes to `on_error` and the bot keeps working.
- **Subscribe only to what is needed.** The bot receives the events you wrote a handler for,
  plus the chat and people joining and leaving.
- **Compatible with Highrise.** The field names and the frame format match the official
  Highrise SDK, so familiar code reads the same.

## Versions and requirements

| What | Value |
|---|---|
| Python | 3.13 and newer |
| Dependencies | `aiohttp` |
| SDK version | 0.3.0 |
| From the bot's owner | an active PREMIUM subscription |
