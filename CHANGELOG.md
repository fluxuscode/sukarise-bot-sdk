**English** | [Русский](CHANGELOG.ru.md) | [Português (Brasil)](CHANGELOG.pt-BR.md)

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow
[semantic versioning](https://semver.org/). While the major version is 0, changes of behaviour
may also come in minor versions; they are always listed here.

## Unreleased

## 0.3.0 — 2026-11-12

### Fixed

- The tags of a channel message: the server counts their length in **bytes** (up to 32) while the
  SDK counted characters, so a tag of 17 Cyrillic letters passed the SDK's check and was refused by
  the server. The SDK now counts bytes.
- Checks before sending against the server's limits: the seat number in `sit_on` is an integer from
  0 to 255, the identifiers of an emote (up to 96 bytes), of furniture and of a conversation (up to
  128), of an item in `buy_item` (up to 256), and an outfit in `wear` has at most 64 items. A wrong
  call raises `InvalidArgument` on the spot instead of a server refusal.
- `wear` and `outfit_problems` wrongly refused outfits in which an item's type cannot be seen from
  its identifier: the server determines the category from the catalog, and for it
  `bag-n_elite2026dazzledbrows` is an eyebrow. Items with identifiers `bag-…` may now make up for a
  missing body part or cover the body, and `wear(await api.outfit_of(...))` works.
- `reconnect=False` silently finished on a temporary HTTP refusal of the connection (for example
  503); a `ConnectionRefused` with `do_not_reconnect=False` is now raised.
- The command `sukarisebot module:Class` did not find the module in the current directory (only
  `python -m sukarisebot` could); now it does.
- The `cooldown` call table grew with every new player; the records of players who have not written
  for a long time are now forgotten.

### Changed

- A server refusal for the rate limit (`Rate limit exceeded for … requests`) arrives before the
  request is carried out, so the SDK repeats the request up to three times with a pause of a
  second. If that does not help, the new `RateLimited`, a subclass of `ResponseError`, is raised:
  an existing `except ResponseError` works as before.
- An HTTP 404 answer on connecting is still retried, but for no more than 5 minutes in a row
  (`Engine(not_found_grace=…)`): after that a `ConnectionRefused` with a hint to check the address.
  Before, a wrong address was retried endlessly.
- People joining and leaving always reach the bot, except in "clean room" mode, so `bot.room` stays
  right even without `on_user_join` and `on_user_leave`. Movements still arrive only when
  `on_user_move` is overridden.
- `--log-level` on the command line accepts only `DEBUG`, `INFO`, `WARNING` and `ERROR`; any other
  value gives a usage error message instead of a traceback.
- `Location` and `Event` are declared as `X | Y` instead of `typing.Union`; nothing changes for
  code that takes them apart with `isinstance` or `match`.

### Added

- The `RateLimited` exception, and the `not_found_grace` and `rate_limit_pause` parameters of
  `Engine`.
- The tests in `tests/test_hardening.py` for everything listed above; the tests got faster (from
  90 to about 17 seconds: the gateway stand-in closes its sockets on shutdown).
- Code checking (`ruff`), building and checking the package, CI in GitHub Actions on Python 3.13
  and 3.14.
- Package metadata: project links, classifiers for the languages of the documentation, an English
  description.
- Documentation in three languages: English (the main one), Russian and Brazilian Portuguese;
  `tests/test_docs.py` checks that the pages, headings, tables, links and code blocks are the same
  in all three.

### Documentation

- Installation: the repository is public, so neither a GitHub account nor `gh` is needed; the
  package is not on PyPI yet. Stale places were fixed: in diagrams and descriptions an HTTP 404 was
  treated as final.
- The section "Language of the texts in the SDK": the descriptions in the code, the exceptions and
  the bot's default phrases are in Russian.

## 0.2.0 — 2026-10-14

- Reconnection: after the server restarts, the bot waits and connects again; `on_start` is called
  on every connection, and `bot.connected` is `False` while it waits.
- A server that is silent for longer than three keepalive intervals (about a minute) is considered
  gone: the bot closes the connection and connects again. Before, the bot could hang on such a
  connection.
- An HTTP 404 answer on connecting is no longer final: the bot retries, because the route may be
  unavailable while the server is being updated. The final refusals are as before: 400, 401, 403
  and "connected from another place".
- The default gateway address: `wss://production-portal-refb.sukarise.ru/web/botapi`.
- Installing from a GitHub release: the file `sukarisebot-0.2.0-py3-none-any.whl` on the release
  page.
- In 3D rooms (worlds) reactions, sitting on furniture, teleport, moderation (kick, ban, unban,
  mute) and tips from the bot (giving) work. Before, the server refused them.
- In 3D the bot hears people's walks and emotes: `on_user_move` and `on_emote` fire there too.
- An emote with an addressee checks that the addressee is in the room, in 3D and in 2D; as before,
  the addressee is not passed in the event.
- People's reactions are not sent by the 3D client, so `on_reaction` does not fire in 3D. The bot
  receives people's tips in 3D rooms as in 2D: `on_tip` fires there too.
- The refusals "…is not available in 3D rooms yet" for reactions, sitting, teleport, moderation and
  tips are no longer given; old servers may still send them.
- New refusals: `That seat is taken`, `The bot is already sitting`, `The bot could not reach that seat`,
  `That user was moved a moment ago`, `The bot is not in this room`.

## 0.1.0

The first version of the SDK.

- The `Bot` class with `on_...` handlers, commands (`@command`), timers (`@every`) and waiting for
  an answer (`wait_for`).
- The `BotAPI` actions: chat and whispers, a hidden channel between bots, emotes and reactions,
  walking, sitting, teleport, moderation, tips and purchases for the bot's gold, direct messages,
  the wallet, the wardrobe and the outfit.
- The room roster `bot.room`, "clean room" mode, the `JsonStore` store, the shared HTTP client
  `bot.http`.
- Testing without a server (`Harness`) and starting from the command line
  (`python -m sukarisebot`).
- Strict typing (`py.typed`, `mypy --strict`, `pyright` strict), descriptions of all public classes,
  methods and fields in Russian, documentation in the `docs/` directory.
- The texts of the SDK's exceptions and the bot's default phrases (the refusal to a non-owner,
  "please wait", `!help`) are in Russian; the bot's phrases are replaced with
  `Bot.phrases = Phrases(...)`.
