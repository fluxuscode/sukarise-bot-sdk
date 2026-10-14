# Команды, таймеры и диалоги

Помимо обработчиков событий у бота есть три удобных механизма: **команды чата**
(`!roll`), **таймеры** (делать что-то каждые N секунд) и **диалоги** (задать вопрос и
дождаться ответа). Все три объявляются прямо в классе бота и не требуют регистрации.

## Команды: `@command`

```python
import random

from sukarisebot import Bot, Context, command


class Dice(Bot):
    @command("roll", aliases=("dice",), cooldown=(3, 60.0), description="бросить кубик")
    async def roll(self, ctx: Context) -> None:
        await ctx.reply(f"@{ctx.user.username} выбросил {random.randint(1, 6)}")

    @command("shutdown", owner_only=True, description="остановить бота")
    async def shutdown(self, ctx: Context) -> None:
        await ctx.reply("Пока!")
        await self.stop()
```

Игрок пишет `!roll` в общий чат или шёпотом — выполняется метод `roll`.

### Как бот понимает команду

- Сообщение должно **начинаться с префикса `!`**. Всё после него делится по пробелам;
  первое слово — имя команды, остальные — аргументы.
- Имя не зависит от регистра: `!Roll`, `!ROLL` и `!roll` — одна команда. Сколько бы
  пробелов ни было между словами, аргументы разделяются по одному.
- Команду находят и в **общем чате**, и в **шёпоте**.
- Своё собственное сообщение бот командой не считает.
- Если такой команды нет, бот молчит, а само сообщение всё равно попадает в `on_chat`.
- Команды выполняются **после** обработчика события чата (`on_chat`/`on_whisper`).

### Параметры `@command`

| Параметр | Описание |
|---|---|
| `name` | имя команды: одно слово без пробелов |
| `aliases` | другие имена той же команды, например `("dice", "кубик")` |
| `description` | короткое описание; его показывает `!help` |
| `cooldown` | `(вызовов, секунд)`: каждому игроку разрешено столько вызовов за любое окно этой длины; сверх лимита бот просит подождать |
| `owner_only` | `True`: команду выполняет только владелец комнаты; остальным бот отвечает отказом |

Неверные параметры (пустое имя, `cooldown=(0, 10)` и т. п.) вызывают `InvalidArgument`
**при определении класса**, а не в разгар работы бота.

Имена и псевдонимы должны быть уникальны: повторное имя — `InvalidArgument`
(«команда … уже зарегистрирована») при создании бота.

### `Context`: что получает команда

Единственный аргумент метода-команды — `Context`:

| Член | Что это |
|---|---|
| `ctx.user` | кто вызвал (`User`) |
| `ctx.name` | каноническое имя команды (даже если вызвана по псевдониму), в нижнем регистре |
| `ctx.args` | кортеж слов после имени |
| `ctx.arg(i)` | `i`-й аргумент или `None`, если его нет |
| `ctx.rest()` | все аргументы одной строкой |
| `ctx.whisper` | `True`, если команда пришла шёпотом |
| `ctx.text` | исходное сообщение целиком |
| `ctx.api` | действия бота (то же, что `self.api`) |
| `await ctx.reply(text)` | ответить **туда, откуда пришла команда**: шёпотом на шёпот, в общий чат на реплику в чате |

Для сообщения `!say привет всем`: `ctx.args == ("привет", "всем")`,
`ctx.arg(0) == "привет"`, `ctx.rest() == "привет всем"`.

```python
from sukarisebot import Bot, Context, command


class Echo(Bot):
    @command("say", description="повторить текст")
    async def say(self, ctx: Context) -> None:
        text = ctx.rest()
        await ctx.reply(text if text else "Что сказать? Напишите: !say текст")
```

### Ограничение частоты (`cooldown`)

`cooldown=(3, 60.0)` — «не больше трёх вызовов за 60 секунд на одного игрока». Это скользящее окно:
игрок, превысивший лимит, получает ответ «подождите N с…», а счётчик освобождается по
мере того, как старые вызовы выходят за окно. Ограничение действует отдельно на каждого
игрока и каждую команду. Вызов, отклонённый из-за `owner_only`, лимит не расходует.

### Только для владельца: `owner_only`

«Владелец» здесь — **владелец комнаты**, в которой работает бот (`bot.owner_id`), а не
владелец бота. Обычно это один человек, но не обязательно. Проверить то же самое в
своём коде можно через `self.is_owner(user)`.

### Команда `!help`

Бот создаёт `!help` сам и перечисляет все команды с описаниями. Команды перечисляются в
порядке **имён методов по алфавиту**, а `!help` стоит последней. Чтобы заменить её
своей, объявите команду `help`:

```python
from sukarisebot import Bot, Context, command


class Polite(Bot):
    @command("help")
    async def help(self, ctx: Context) -> None:
        await ctx.reply("Напишите !roll, чтобы бросить кубик.")
```

### Что бот говорит сам: `Phrases`

Три фразы бот произносит от своего имени: отказ не-владельцу, просьбу подождать и
ответ на `!help`. По умолчанию они русские. Заменить их можно, задав в классе бота
атрибут `phrases`:

```python
from sukarisebot import Bot, Phrases


class English(Bot):
    phrases = Phrases(
        owner_only="@{username}, {prefix}{command} is for the room owner.",
        cooldown="@{username}, wait {seconds} s before {prefix}{command} again.",
        help="Commands: {commands}",
    )
```

| Поле `Phrases` | Когда используется | Поля шаблона |
|---|---|---|
| `owner_only` | не-владелец вызвал команду `owner_only` | `{username}`, `{prefix}`, `{command}` |
| `cooldown` | команду вызвали слишком часто | `{username}`, `{prefix}`, `{command}`, `{seconds}` |
| `help` | ответ на `!help` | `{commands}` — список команд |
| `help_separator` | разделитель команд в списке | — |

Шаблон форматируется методом `str.format`: используйте только перечисленные поля.
Неизвестное поле вызовет `KeyError`, который попадёт в `on_error`.

## Таймеры: `@every`

```python
from sukarisebot import Bot, every


class Herald(Bot):
    @every(300)
    async def announce(self) -> None:
        await self.api.chat("Не забывайте про правила комнаты.")
```

`@every(seconds)` запускает метод каждые `seconds` секунд, пока бот подключён.

- Метод не принимает аргументов (кроме `self`).
- **Первый запуск** — через `seconds` секунд после подключения, а не сразу.
- Следующий запуск отсчитывается от *конца* предыдущего, поэтому реальный период —
  `seconds` плюс время работы метода. Запуски одного таймера не накладываются.
- Ошибка в таймере не останавливает его: она уходит в [`on_error`](handlers.md#on_error)
  (с `event=None`).
- Пока соединения нет, запуски пропускаются. При переподключении таймеры не
  перезапускаются, а продолжают идти.
- Таймер работает в отдельной задаче, поэтому он может выполняться, пока обработчик
  события ждёт на `await`.
- `seconds` должен быть положительным конечным числом, иначе `InvalidArgument`.

## Диалоги: `wait_for`

`await self.wait_for(kind, check, timeout=...)` ждёт **следующее** событие типа `kind`,
которое проходит проверку `check`. Идеально для «задал вопрос — жду ответ»:

```python
from sukarisebot import Bot, ChatEvent, Context, command


class Riddle(Bot):
    @command("riddle", cooldown=(1, 60.0), description="загадка")
    async def riddle(self, ctx: Context) -> None:
        await ctx.reply("Зимой и летом одним цветом. Что это? Ответьте шёпотом.")
        try:
            answer = await self.wait_for(
                ChatEvent,
                lambda event: event.whisper and event.user.id == ctx.user.id,
                timeout=60,
            )
        except TimeoutError:
            await ctx.reply("Время вышло.")
            return
        if answer.message.strip().lower() == "ёлка":
            await ctx.reply("Верно!")
        else:
            await ctx.reply("Неверно.")
```

| Параметр | Описание |
|---|---|
| `kind` | класс события: `ChatEvent`, `UserJoinedEvent` и т. д. |
| `check` | функция «подходит ли событие»; `None` — подходит любое |
| `timeout` | сколько секунд ждать; по истечении — `TimeoutError` |

Что нужно знать:

1. **Всегда задавайте `timeout`.** Без него ожидание может не закончиться никогда.
2. **Пока команда ждёт, бот не обрабатывает другие события.** Обработчики идут по одному
   (см. [«Устройство SDK»](architecture.md#как-событие-доходит-до-обработчика)); ждущая
   команда занимает очередь. Для диалога с одним игроком в тихой комнате это нормально;
   для нескольких игроков одновременно запускайте диалог отдельной задачей (ниже).
3. **`wait_for` видит только события, пришедшие после вызова.** Ответ, который уже пришёл
   и стоит в очереди раньше, чем команда дошла до `wait_for`, пропущен: так бывает,
   когда игрок пишет ответ мгновенно, а бот отстаёт. Сначала задайте вопрос, потом ждите.
4. **Ожидание срабатывает в момент прихода события**, до очереди, поэтому нужное событие
   ждущая команда увидит, даже сама занимая очередь. После этого событие обычным
   порядком попадёт и в обработчики `on_...` (в том числе `on_whisper`), и в команды.
5. **Событие должно приходить боту.** Чат доставляется всегда. Чтобы дождаться любого
   другого события, переопределите его обработчик (достаточно пустого), иначе подписки
   на него нет.
6. Если функция `check` выбросит исключение, оно выйдет из `wait_for` в вашем коде.

### Диалоги с несколькими игроками одновременно

Запустите диалог отдельной задачей, чтобы команда завершилась сразу и очередь событий не
блокировалась. Не забудьте держать ссылку на задачу и передавать её ошибки в `on_error`:

```python
import asyncio
from collections.abc import Awaitable

from sukarisebot import Bot, ChatEvent, Context, command


class Quiz(Bot):
    def __init__(self) -> None:
        super().__init__()
        self._dialogs: set[asyncio.Task[None]] = set()

    def spawn(self, work: Awaitable[None]) -> None:
        """Запустить диалог в фоне: ссылка хранится, ошибки уходят в on_error."""
        task = asyncio.create_task(self._guarded(work))
        self._dialogs.add(task)
        task.add_done_callback(self._dialogs.discard)

    async def _guarded(self, work: Awaitable[None]) -> None:
        try:
            await work
        except Exception as error:
            await self.on_error(error, None)

    @command("quiz", cooldown=(1, 30.0), description="викторина")
    async def quiz(self, ctx: Context) -> None:
        self.spawn(self._ask(ctx))  # команда завершается сразу

    async def _ask(self, ctx: Context) -> None:
        await ctx.api.whisper(ctx.user.id, "Сколько будет 6 x 7?")
        try:
            answer = await self.wait_for(
                ChatEvent,
                lambda event: event.whisper and event.user.id == ctx.user.id,
                timeout=60,
            )
        except TimeoutError:
            await ctx.api.whisper(ctx.user.id, "Время вышло.")
            return
        verdict = "Верно!" if answer.message.strip() == "42" else "Неверно."
        await ctx.api.whisper(ctx.user.id, verdict)
```

## Данные в памяти: `state` и `user_state`

- `self.state` — свободный словарь `dict[str, object]` для данных бота.
- `self.user_state(user_id)` — личный словарь на игрока; создаётся при первом обращении.

Оба живут, пока работает процесс, и **не сохраняются на диск**. Для данных, которые
должны пережить перезапуск, используйте [`JsonStore`](tools.md#jsonstore-данные-между-запусками).

```python
from sukarisebot import Bot, Context, command


class Counter(Bot):
    @command("count", description="посчитать мои вызовы")
    async def count(self, ctx: Context) -> None:
        state = self.user_state(ctx.user.id)
        calls = state.get("calls", 0)
        calls = (calls if isinstance(calls, int) else 0) + 1
        state["calls"] = calls
        await ctx.reply(f"@{ctx.user.username}, вы вызвали меня {calls} раз(а).")
```

## Как проверить команды в тестах

Команды и диалоги проверяются без сервера через `Harness`; диалог с `wait_for` запускайте
отдельной задачей — см. [«Тестирование»](testing.md).
