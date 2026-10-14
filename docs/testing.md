# Тестирование без сервера

`Harness` запускает бота **в памяти**: сети нет, ждать таймеры не нужно, комната
изображается заготовками. Вы подаёте боту события (`say`, `join`, `emit`), а потом
проверяете, что бот попытался сделать (`chats`, `whispers`, `requests`).

```python
import asyncio

from sukarisebot import Bot, Location, User
from sukarisebot.testing import Harness


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Добро пожаловать, {user.username}!")


def test_greeting() -> None:
    async def scenario() -> None:
        harness = Harness(Greeter())
        await harness.start()
        await harness.join("alice")
        assert harness.chats == ["Добро пожаловать, alice!"]

    asyncio.run(scenario())
```

Тесты запускаются обычным `pytest`. Дополнительные плагины для асинхронных тестов не
нужны: сценарий оборачивается в `asyncio.run(...)`.

## Как это устроено

`Harness` подключает бота не к серверу, а к «записывающему серверу» —
`RecordingRequester`. Все действия бота (`self.api.chat(...)` и др.) не уходят в сеть, а
записываются в список `harness.requester.sent`. События, которые вы подаёте, проходят
тот же путь, что и в настоящем подключении: сначала срабатывает ожидание `wait_for`,
затем обработчики `on_...` и команды.

## Подача событий

| Метод | Что делает |
|---|---|
| `await harness.start()` | «Подключает» бота: вызывает `on_start`, загружает состав комнаты (если не «чистая комната») |
| `await harness.say(username, text, whisper=False)` | пользователь пишет в чат (или шепчет боту) |
| `await harness.join(username, position)` | пользователь входит: попадает в состав комнаты и приходит `UserJoinedEvent` |
| `await harness.leave(user)` | пользователь выходит |
| `await harness.emit(event)` | подать любое событие: `EmoteEvent`, `ModerationEvent`, `MessageEvent` и т. д. |
| `harness.event_tip(sender, receiver, item)` | собрать `TipEvent`, чтобы подать его через `emit` |

Идентификатор пользователя в тесте — `"user-" + username`. Каждый вызов возвращается,
когда бот закончил обработку события.

## Проверка результата

| Член | Что возвращает |
|---|---|
| `harness.chats` | реплики бота в общий чат, по порядку |
| `harness.whispers` | шёпоты бота, по порядку |
| `harness.requests("ModerateRoomRequest")` | все запросы одного вида (`Sent`) |
| `harness.requester.sent` | все запросы по порядку |
| `harness.bot` | сам бот: проверяйте `bot.room`, `bot.state` и т. д. |

`Sent` — запись одного запроса: `kind` (например, `"ChatRequest"`), `category` (лимит) и
`body` (поля). Какие запросы отправляет каждый метод — в [«Протоколе»](protocol.md).

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

Здесь `owner_id="user-boss"` делает пользователя `boss` владельцем комнаты (его
идентификатор в тесте — `user-boss`).

## Настройка «сервера»

Что «знает сервер» — поля `harness.requester`:

| Поле | Что задаёт |
|---|---|
| `room` | состав комнаты (его заполняет `harness.join`) |
| `gold` | золото в кошельке бота |
| `inventory` | гардероб бота |
| `permissions` | права, которые вернёт `privileges` |
| `tips_paid` | `False`: чаевые и покупки отвечают «не хватило золота» |
| `conversation_frames`, `message_frames` | кадры личных диалогов и сообщений |
| `refuse_with` | любой запрос отклоняется `ResponseError` с этим текстом |

```python
import asyncio

from sukarisebot import Bot, Context, ResponseError, command
from sukarisebot.testing import Harness


class Tipper(Bot):
    @command("tipme")
    async def tipme(self, ctx: Context) -> None:
        if await self.api.tip(ctx.user.id, "gold_bar_10"):
            await ctx.reply("Держите!")
        else:
            await ctx.reply("Золота не хватает.")


def test_a_poor_bot_says_so() -> None:
    async def scenario() -> None:
        harness = Harness(Tipper())
        harness.requester.tips_paid = False
        await harness.start()
        await harness.say("alice", "!tipme")
        assert harness.chats == ["Золота не хватает."]

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

## Чаевые и личные сообщения

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
                "content": "привет",
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
        assert reply.body["content"] == "ПРИВЕТ"

    asyncio.run(scenario())
```

## Диалоги с `wait_for`

Команда, которая ждёт ответ, не завершится, пока ответ не придёт. Поэтому в тесте
запускайте её отдельной задачей, дайте ей начать ждать, подайте ответ и дождитесь задачи:

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
        await ctx.reply(f"Вы ответили: {answer.message}")


def test_a_dialog() -> None:
    async def scenario() -> None:
        harness = Harness(Asker())
        await harness.start()
        task = asyncio.create_task(harness.say("alice", "!ask"))
        await asyncio.sleep(0)  # дать команде дойти до wait_for
        await harness.say("alice", "42", whisper=True)
        await task
        assert harness.chats == ["Вы ответили: 42"]

    asyncio.run(scenario())
```

## Таймеры

Harness **не запускает** таймеры `@every`: ждать их в тесте незачем. Проверяйте метод
напрямую:

```python
import asyncio

from sukarisebot import Bot, every
from sukarisebot.testing import Harness


class Herald(Bot):
    @every(300)
    async def announce(self) -> None:
        await self.api.chat("Правила комнаты: будьте вежливы.")


def test_the_announcement() -> None:
    async def scenario() -> None:
        bot = Herald()
        harness = Harness(bot)
        await harness.start()
        await bot.announce()
        assert harness.chats == ["Правила комнаты: будьте вежливы."]

    asyncio.run(scenario())
```

## Чего Harness не делает

- Не проверяет **правила сервера**: права модератора, наличие человека в комнате, лимиты
  золота. Эти отказы имитируйте полями `refuse_with` и `tips_paid`.
- Не фильтрует события по подпискам: в `emit` можно подать любое событие, даже если у бота нет
  соответствующего обработчика (тогда оно просто ничего не вызовет).
- Не применяет лимиты частоты и не использует сеть.
- Не проверяет протокол. За это отвечает отдельный набор тестов самого SDK на настоящем
  websocket (каталог `tests/` репозитория, `fake_gateway.py`).

Перед запуском бота на настоящем сервере удобно один раз проверить его в тестовой
комнате.
