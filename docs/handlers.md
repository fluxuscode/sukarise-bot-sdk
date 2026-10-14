# Обработчики событий

Обработчик — это метод класса бота вида `async def on_...`. Все они определены в
`Bot` и **по умолчанию ничего не делают**, поэтому вы переопределяете только нужные.

```python
from sukarisebot import Bot, Location, User


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Привет, {user.username}!")
```

Правила, общие для всех обработчиков:

- Метод обязан быть `async def`. Сигнатуру берите из таблицы ниже; в PyCharm её
  сгенерирует **Code → Override Methods** (`Ctrl+O`) вместе с описанием.
- SDK подписывает бота **только на те события, для которых есть переопределённый
  обработчик**. Лишний трафик не приходит. Подробнее — [«Устройство SDK»](architecture.md#подписки-на-события).
- События обрабатываются **по одному, в порядке прихода**. Пока обработчик не
  завершился, следующее событие ждёт. Долгую работу выносите в задачи.
- Исключение внутри обработчика не останавливает бота: оно передаётся в `on_error`.
- Сигнатуру менять нельзя: SDK вызывает обработчики позиционными аргументами в
  том порядке, который указан здесь.

## Сводная таблица

| Обработчик | Когда вызывается | Событие | Подписка | В 3D |
|---|---|---|---|---|
| [`on_start(session)`](#on_start) | бот вошёл в комнату; снова после каждого переподключения | `SessionMetadata` | — | да |
| [`on_chat(user, message)`](#on_chat) | реплика в общем чате | `ChatEvent` | `chat` | да |
| [`on_whisper(user, message)`](#on_whisper) | шёпот, адресованный боту | `ChatEvent` | `chat` | да |
| [`on_emote(user, emote_id, receiver)`](#on_emote) | кто-то сыграл эмоцию | `EmoteEvent` | `emote` | да |
| [`on_reaction(user, reaction, receiver)`](#on_reaction) | один игрок отправил реакцию другому | `ReactionEvent` | `reaction` | нет |
| [`on_user_join(user, position)`](#on_user_join) | кто-то вошёл в комнату | `UserJoinedEvent` | `user_joined` | да |
| [`on_user_leave(user)`](#on_user_leave) | кто-то вышел | `UserLeftEvent` | `user_left` | да |
| [`on_user_move(user, position)`](#on_user_move) | кто-то пошёл или сел (в 3D — пошёл) | `UserMovedEvent` | `user_moved` | да |
| [`on_channel(sender_id, message, tags)`](#on_channel) | скрытое сообщение от другого бота | `ChannelEvent` | `channel` | да |
| [`on_moderate(moderator_id, target_user_id, moderation_type, duration)`](#on_moderate) | модерация в комнате | `ModerationEvent` | `moderation` | да |
| [`on_tip(sender, receiver, item)`](#on_tip) | чаевые в комнате | `TipEvent` | `tip_reaction` | да |
| [`on_message(user_id, conversation_id, is_new_conversation)`](#on_message) | человек написал боту личное сообщение | `MessageEvent` | `message` | да |
| [`on_error(error, event)`](#on_error) | обработчик, команда или таймер упали | — | — | — |

В 3D-комнате боту приходят события, отмеченные в последней колонке словом «да»: чат и
шёпот, вход и выход людей, ходьба и эмоции людей, модерация, скрытые сообщения других ботов
и личные сообщения. Реакции людей в 3D до бота не доходят: 3D-клиент их не
отправляет. Чаевые людей доходят и в 3D. Положение людей бот узнаёт из событий ходьбы и запросом `list_room_users()`
(или `await self.refresh_room()`).

## Каждый обработчик подробно

### `on_start`

```python
async def on_start(self, session: SessionMetadata) -> None
```

Бот вошёл в комнату. Вызывается **после каждого (пере)подключения**, поэтому пишите его
так, чтобы повторный вызов не вредил (например, не запускайте здесь бесконечные циклы).
К этому моменту `bot.room` уже заполнен (если не включён режим «чистой комнаты»).
Хорошее место для приветствия и для первичной настройки.

- `session` — кто бот (`session.user_id`), в какой он комнате
  (`session.room_info.room_name`, `.owner_id`) и какие лимиты частоты действуют.

### `on_chat`

```python
async def on_chat(self, user: User, message: str) -> None
```

Реплика в общем чате комнаты. Вызывается для любой реплики, в том числе для сообщений-команд
(`!roll`): команда выполняется отдельно, после этого обработчика. Реплики самого бота
в 2D-комнате сервер боту не присылает, а команды, написанные самим ботом, SDK не выполняет.

### `on_whisper`

```python
async def on_whisper(self, user: User, message: str) -> None
```

Шёпот, адресованный боту (в комнате). Шёпоты других людей между собой бот не видит.
Не путайте с личными сообщениями в диалогах — те приходят в [`on_message`](#on_message).

### `on_emote`

```python
async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None
```

Кто-то сыграл эмоцию. `receiver` — тот, на кого она направлена, или `None`, если ни на
кого.

### `on_reaction`

```python
async def on_reaction(self, user: User, reaction: str, receiver: User) -> None
```

Один игрок отправил другому реакцию: `clap`, `heart`, `thumbs`, `wave` или `wink`.
Параметр `reaction` — обычная строка (не `Literal`): так код не ломается, если сервер
когда-нибудь добавит новую реакцию.

### `on_user_join`

```python
async def on_user_join(self, user: User, position: Location) -> None
```

В комнату вошёл пользователь. `position` — где он появился: `Position` (точка на полу)
или `AnchorPosition` (место на мебели).

### `on_user_leave`

```python
async def on_user_leave(self, user: User) -> None
```

Пользователь вышел из комнаты.

### `on_user_move`

```python
async def on_user_move(self, user: User, position: Location) -> None
```

Пользователь пошёл в другую точку или сел. В оживлённой комнате события идут часто;
подписывайтесь, только если они нужны.

### `on_channel`

```python
async def on_channel(self, sender_id: str, message: str, tags: tuple[str, ...]) -> None
```

Скрытое сообщение от другого бота в этой комнате (см. [`BotAPI.channel`](api.md#channel)).
Игроки такие сообщения не видят. Собственные сообщения бот не получает.

### `on_moderate`

```python
async def on_moderate(
    self,
    moderator_id: str,
    target_user_id: str,
    moderation_type: str,
    duration: int | None,
) -> None
```

В комнате выполнено действие модерации: `moderation_type` — `kick`, `ban`, `unban` или
`mute`; `duration` — срок в секундах или `None`. О действиях, которые бот выполнил сам,
он не уведомляется. Если наказан сам бот, `target_user_id` равен `bot.session.user_id`.

### `on_tip`

```python
async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None
```

Кто-то дал кому-то чаевые. **Событие приходит о любых чаевых в комнате**, а не только о
чаевых боту. Чаевые именно боту — те, у которых `receiver.id == self.session.user_id`.

`item` — это либо `CurrencyItem` (золото: `item.amount` — сколько золота получил
адресат), либо `Item` (предмет). Боту чаевые всегда приходят **золотом**: стоимость
слитка зачисляется на кошелёк бота (`gold_bar_10` даёт 10 золота). Владелец забирает
накопленное золото в личном кабинете. Пример — [`examples/tipping_bot.py`](../examples/tipping_bot.py).

```python
from sukarisebot import Bot, CurrencyItem, Item, User


class Thanks(Bot):
    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        if self.session is None or receiver.id != self.session.user_id:
            return  # чаевые не боту
        if isinstance(item, CurrencyItem):
            await self.api.chat(f"Спасибо, {sender.username}, за {item.amount} золота!")
```

### `on_message`

```python
async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None
```

Человек написал боту **личное сообщение** (в диалоге вне комнаты). В событии нет текста:
прочитайте его через `await self.api.messages(conversation_id)` (новые сообщения
первыми), ответьте через `await self.api.send_message(conversation_id, "…")`.

- Запрос на диалог принимается за бота автоматически.
- Первым бот в диалог не пишет: начинает человек.
- Бот участвует только в личных диалогах (не в группах).

```python
from sukarisebot import Bot


class Echo(Bot):
    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        messages = await self.api.messages(conversation_id)
        if messages and messages[0].sender_id == user_id:
            await self.api.send_message(conversation_id, f"Вы написали: {messages[0].content}")
```

### `on_error`

```python
async def on_error(self, error: Exception, event: Event | None) -> None
```

Обработчик, команда или таймер выбросили исключение. По умолчанию ошибка пишется в
журнал `sukarisebot` вместе с трассировкой. Переопределите метод, чтобы, например,
сообщить владельцу:

```python
from sukarisebot import Bot, Event


class Careful(Bot):
    async def on_error(self, error: Exception, event: Event | None) -> None:
        await super().on_error(error, event)  # оставить запись в журнале
        if self.owner_id is not None and self.owner_id in self.room:
            await self.api.whisper(self.owner_id, f"Ошибка: {error}")
```

`event` — событие, при обработке которого возникла ошибка. Для команды это событие чата,
которое её вызвало; `None` — для таймера и для ошибки в `on_start`. Если упадёт и
сам `on_error`, это попадёт в журнал, а бот продолжит работу.

## Какое событие какой обработчик получает

Чат разделён на два обработчика: одно и то же событие `ChatEvent` попадает в `on_chat`,
если `whisper=False`, и в `on_whisper`, если `whisper=True`. Остальные события связаны с
обработчиками один к одному. Во всех случаях команды (`@command`) выполняются **после**
обработчика события чата.

## Что делать с событием, для которого нет обработчика

Ничего: если обработчик не переопределён, SDK не подписывается на это событие, и оно
вообще не приходит. Это касается и [`wait_for`](commands.md#диалоги-wait_for): чат
доставляется всегда (подписка на него включена ради команд), а чтобы дождаться любого
другого события, переопределите его обработчик — достаточно пустого
(`async def on_emote(...): pass`), иначе подписки не будет и `wait_for` не дождётся.
