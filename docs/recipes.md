# Рецепты

Готовые решения типичных задач. Каждый рецепт — законченный бот; его можно сохранить в
файл и запустить (`python -m sukarisebot файл:Класс`). Ещё примеры лежат в каталоге
[`examples/`](../examples/).

## Приветствие с запоминанием

Здоровается с новичками иначе, чем с постоянными гостями. Запоминает визиты между
запусками.

```python
from pathlib import Path

from sukarisebot import Bot, JsonStore, JsonValue, Location, User


def count_visit(old: JsonValue) -> JsonValue:
    visits = old if isinstance(old, int) else 0
    return visits + 1


class Host(Bot):
    def __init__(self, path: str | Path = "visits.json") -> None:
        super().__init__()
        self.store = JsonStore(path)

    async def on_user_join(self, user: User, position: Location) -> None:
        visits = await self.store.update(user.id, count_visit)
        if visits == 1:
            await self.api.chat(f"Добро пожаловать, {user.username}! Рады новому гостю.")
        else:
            await self.api.chat(f"С возвращением, {user.username}! Это ваш визит номер {visits}.")
```

## Благодарность за чаевые боту

Благодарит только за **чаевые боту** (а не между другими людьми) и считает золото.
Золото боту приходит на кошелёк, владелец забирает его в личном кабинете.

```python
from sukarisebot import Bot, CurrencyItem, Item, User


class Thanks(Bot):
    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        if self.session is None or receiver.id != self.session.user_id:
            return  # чаевые не боту
        if isinstance(item, CurrencyItem):
            total = await self.api.gold()
            await self.api.chat(f"Спасибо, {sender.username}! Теперь у меня {total} золота.")
```

Более полная версия с таблицей лидеров — [`examples/tipping_bot.py`](../examples/tipping_bot.py).

## Ответы на личные сообщения

Человек пишет боту в личные сообщения; бот отвечает на последнее сообщение.

```python
from sukarisebot import Bot


class Receptionist(Bot):
    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        if is_new_conversation:
            await self.api.send_message(conversation_id, "Здравствуйте! Я бот комнаты. Напишите «правила».")
            return
        messages = await self.api.messages(conversation_id)
        if not messages or messages[0].sender_id != user_id:
            return
        if "правила" in messages[0].content.lower():
            await self.api.send_message(conversation_id, "1. Будьте вежливы. 2. Без спама.")
        else:
            await self.api.send_message(conversation_id, "Не понял. Напишите «правила».")
```

Помните: первым бот в диалог не пишет — начинает человек.

## Модератор: молчание за спам

Бот должен быть **модератором** комнаты (не только дизайнером).

```python
import time
from collections import defaultdict, deque

from sukarisebot import Bot, ResponseError, User

LIMIT = 5  # сообщений
WINDOW = 10.0  # секунд


class AntiSpam(Bot):
    def __init__(self) -> None:
        super().__init__()
        self._recent: defaultdict[str, deque[float]] = defaultdict(deque)

    async def on_chat(self, user: User, message: str) -> None:
        if self.is_owner(user):
            return
        now = time.monotonic()
        recent = self._recent[user.id]
        recent.append(now)
        while recent and now - recent[0] > WINDOW:
            recent.popleft()
        if len(recent) > LIMIT:
            recent.clear()
            try:
                await self.api.mute(user.id, 60)
                await self.api.chat(f"{user.username}, пожалуйста, не спамьте. Минута тишины.")
            except ResponseError as error:
                await self.api.chat(f"Не могу заглушить: {error.message}")
```

## Копировать наряд игрока

По команде `!copyme` бот надевает наряд того, кто попросил. Смена наряда бесплатна,
пока у владельца бота активный PREMIUM.

```python
from sukarisebot import Bot, Context, InvalidArgument, ResponseError, command


class Mirror(Bot):
    @command("copyme", cooldown=(1, 30.0), description="надеть мой наряд")
    async def copyme(self, ctx: Context) -> None:
        outfit = await ctx.api.outfit_of(ctx.user.id)
        try:
            await ctx.api.wear(outfit)
        except InvalidArgument as error:
            await ctx.reply(f"Этот наряд надеть нельзя: {error}")
        except ResponseError as error:
            await ctx.reply(f"Не получилось: {error.message}")
        else:
            await ctx.reply("Готово!")
```

## Бот-распорядитель: усаживает гостей

Когда игрок садится на мебель, бот садится на соседнее место той же мебели (если оно
свободно). Показывает работу с `Location`.

```python
from sukarisebot import AnchorPosition, Bot, Location, ResponseError, User


class Companion(Bot):
    async def on_user_move(self, user: User, position: Location) -> None:
        if not isinstance(position, AnchorPosition):
            return
        neighbour = AnchorPosition(position.entity_id, position.anchor_ix + 1)
        try:
            await self.api.sit_on(neighbour)
        except ResponseError:
            pass  # соседнего места нет или оно занято
```

## Объявление по расписанию

```python
from sukarisebot import Bot, every


class Herald(Bot):
    @every(600)
    async def rules(self) -> None:
        await self.api.chat("Напоминание: в комнате действуют правила. Команды — !help.")
```

## Два бота в одной комнате договариваются

Один бот сообщает другому через скрытый канал (игроки не видят):

```python
from sukarisebot import Bot, Context, command


class Boss(Bot):
    @command("alarm", owner_only=True, description="поднять тревогу у всех ботов")
    async def alarm(self, ctx: Context) -> None:
        await self.api.channel("alarm", tags=["security"])
        await ctx.reply("Сигнал отправлен.")


class Worker(Bot):
    async def on_channel(self, sender_id: str, message: str, tags: tuple[str, ...]) -> None:
        if message == "alarm" and "security" in tags:
            await self.api.chat("Тревога! Всем сохранять спокойствие.")
```

Каждый из ботов запускается своим токеном (у каждого — свой процесс или своя задача).
Оба должны быть в одной комнате.

## Запрос к внешнему сервису

```python
from sukarisebot import Bot, Context, command


class Fact(Bot):
    @command("fact", cooldown=(1, 20.0), description="случайный факт")
    async def fact(self, ctx: Context) -> None:
        # Адрес вымышленный: подставьте свой сервис.
        async with self.http.get("https://example.com/api/fact") as response:
            if response.status != 200:
                await ctx.reply("Сервис фактов недоступен.")
                return
            await ctx.reply((await response.text())[:300])
```

Не делайте блокирующих вызовов (`requests`, `time.sleep`): они остановят весь бот. Используйте
`self.http` и `await asyncio.sleep(...)`.
