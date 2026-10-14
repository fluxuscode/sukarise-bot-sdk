# Справочник действий `BotAPI`

Всё, что бот умеет делать, — методы объекта `BotAPI`. В работающем боте он доступен как
`self.api`, а в команде ещё и как `ctx.api`. Каждый метод — **одно асинхронное
действие**: вызывайте его через `await`.

```python
await self.api.chat("Привет!")
users = await self.api.list_room_users()
```

## Общие правила

**Проверка до отправки.** Аргументы проверяются заранее. Пустой текст, неизвестная
реакция, координата вне допустимого диапазона дают `InvalidArgument` в вашей строке кода —
запрос при этом не уходит.

**Исключения.** Любой метод может выбросить:

| Исключение | Когда |
|---|---|
| `InvalidArgument` | аргумент неверен; запрос не отправлялся |
| `ResponseError` | сервер отказал (нет прав, человека нет в комнате, не поддерживается в 3D и т. п.); текст отказа — в `error.message` по-английски |
| `NotConnected` | у бота нет соединения |
| `RequestTimeout` | сервер не ответил за 10 секунд |

В таблицах ниже перечислены только причины, специфичные для метода. Подробности —
[«Ошибки и отказы»](errors.md).

**Лимиты частоты.** У каждого метода есть категория лимита (колонка «Лимит»). Если бюджет
исчерпан, SDK сам подождёт; отказа по лимиту бот обычно не видит. См.
[«Устройство SDK»](architecture.md#лимиты-частоты).

**2D и 3D.** Бот работает в обычных (2D) и в 3D-комнатах. Колонка «Комнаты» показывает, где
метод доступен; в 3D-мире бот получает то же, что в 2D, кроме реакций людей, которые
клиент там не отправляет (см. [«Что работает и что нет»](../README.md)).

## Сводка

| Метод | Что делает | Лимит | Комнаты |
|---|---|---|---|
| [`chat(message)`](#chat) | сказать в общий чат | `chat` | 2D, 3D |
| [`whisper(user_id, message)`](#whisper) | шёпот одному человеку | `chat` | 2D, 3D |
| [`channel(message, tags, only_to)`](#channel) | скрытое сообщение другим ботам | `channel` | 2D, 3D |
| [`emote(emote_id, target_user_id)`](#emote) | сыграть эмоцию | `emote` | 2D, 3D |
| [`react(reaction, target_user_id)`](#react) | отправить реакцию | `emote` | 2D, 3D |
| [`move_to(position)`](#move_to) | пойти в точку | `move` | 2D, 3D |
| [`sit_on(anchor)`](#sit_on) | сесть на место мебели | `move` | 2D, 3D |
| [`teleport_user(user_id, position)`](#teleport_user) | переместить человека | `teleport` | 2D, 3D |
| [`list_room_users()`](#list_room_users) | кто в комнате и где | `info` | 2D, 3D |
| [`privileges(user_id)`](#privileges) | права человека в комнате | `info` | 2D, 3D |
| [`set_privileges(user_id, moderator, designer)`](#set_privileges) | выдать/отобрать права | `moderate` | всегда отказ на SukaRise |
| [`moderate(user_id, action, seconds)`](#moderate) | kick/ban/unban/mute | `moderate` | 2D, 3D |
| [`kick(user_id)`](#kick) | выгнать | `moderate` | 2D, 3D |
| [`ban(user_id, seconds)`](#ban) | заблокировать | `moderate` | 2D, 3D |
| [`unban(user_id)`](#unban) | снять блокировку | `moderate` | 2D, 3D |
| [`mute(user_id, seconds)`](#mute) | заглушить | `moderate` | 2D, 3D |
| [`tip(user_id, gold_bar)`](#tip) | чаевые золотом бота | `tip` | 2D, 3D |
| [`buy_item(item_id)`](#buy_item) | купить предмет за золото бота | `shop` | 2D, 3D |
| [`conversations(not_joined, last_id)`](#conversations) | личные диалоги бота | `info` | 2D, 3D |
| [`messages(conversation_id, last_message_id)`](#messages) | сообщения диалога | `info` | 2D, 3D |
| [`send_message(conversation_id, content)`](#send_message) | ответить в диалоге | `message` | 2D, 3D |
| [`send_bulk_message(user_ids, content)`](#send_bulk_message) | написать многим | `message` | 2D, 3D |
| [`leave_conversation(conversation_id)`](#leave_conversation) | выйти из диалога | `message` | 2D, 3D |
| [`wallet()`](#wallet) | все валюты бота | `info` | 2D, 3D |
| [`gold()`](#gold) | золото бота | `info` | 2D, 3D |
| [`outfit_of(user_id)`](#outfit_of) | наряд человека | `info` | 2D, 3D |
| [`inventory()`](#inventory) | гардероб бота | `info` | 2D, 3D |
| [`wear(items)`](#wear) | сменить наряд бота | `info` | 2D, 3D |
| [`split_message(text, limit)`](#split_message) | разрезать длинный текст | — | вспомогательная функция |

## Чат

### `chat`

```python
async def chat(self, message: str) -> None
```

Сказать фразу в общий чат комнаты. Текст длиннее **500 символов** режется по пробелам и
уходит несколькими сообщениями подряд.

| Параметр | Описание |
|---|---|
| `message` | текст реплики |

`InvalidArgument` — текст пустой или из одних пробелов. `ResponseError` — например, бота
заглушили.

```python
await self.api.chat("Всем привет!")
```

### `whisper`

```python
async def whisper(self, user_id: str, message: str) -> None
```

Личное сообщение одному человеку **в комнате**. Его видят только получатель и бот.
Длинный текст режется на несколько шёпотов.

| Параметр | Описание |
|---|---|
| `user_id` | получатель; должен быть в комнате |
| `message` | текст |

`ResponseError` — получателя нет в комнате. Для сообщений людям, которых в комнате
нет, используйте личные диалоги ([`send_message`](#send_message)).

### `channel`

```python
async def channel(
    self,
    message: str,
    *,
    tags: Iterable[str] = (),
    only_to: Iterable[str] | None = None,
) -> None
```

Скрытое сообщение другим **ботам** в этой комнате. Игроки его не видят. Получатели
услышат его в [`on_channel`](handlers.md#on_channel); сам отправитель своё сообщение
не получает. Так боты в одной комнате могут договариваться.

| Параметр | Описание |
|---|---|
| `message` | текст, не больше **1024 байт** в UTF-8 |
| `tags` | метки, до 10 штук по 32 символа; по ним получатели отбирают сообщения |
| `only_to` | идентификаторы ботов-адресатов (до 50); `None` — всем ботам комнаты |

## Язык тела

### `emote`

```python
async def emote(self, emote_id: str, *, target_user_id: str | None = None) -> None
```

Сыграть эмоцию: самому или в сторону человека. **Платные эмоции бот играет бесплатно,
если у его владельца активный PREMIUM.** Парные эмоции (с партнёром) боту недоступны.

| Параметр | Описание |
|---|---|
| `emote_id` | идентификатор эмоции, например `"emote-wave"` |
| `target_user_id` | на кого направить; `None` — ни на кого. Адресат должен быть в комнате (в 3D тоже); как и в 2D, эмоция его в событии не передаёт |

`ResponseError` — такой эмоции нет, она парная, платная при отсутствии PREMIUM у
владельца, или адресата нет в комнате.

### `react`

```python
async def react(self, reaction: Reaction, target_user_id: str) -> None
```

Отправить человеку реакцию: `"clap"` (аплодисменты), `"heart"` (сердце), `"thumbs"`
(палец вверх), `"wave"` (приветствие), `"wink"` (подмигивание).

`InvalidArgument` — неизвестная реакция. `ResponseError` — адресата нет в комнате.

```python
await self.api.react("heart", user.id)
```

## Движение

### `move_to`

```python
async def move_to(self, position: Position) -> None
```

Отправить бота пешком в точку на полу. Координаты — конечные числа в пределах **±1000**;
направление `facing` — `FrontRight`, `FrontLeft`, `BackRight` или `BackLeft`.

```python
from sukarisebot import Position

await self.api.move_to(Position(5.5, 0.0, 5.5, facing="FrontLeft"))
```

**В 3D-мире у ходьбы нет ответа.** Запрос уходит и считается выполненным, даже если мир не
может проложить путь (точка за мебелью или вне пола): бот тогда просто остаётся на месте и
`ResponseError` не приходит. Если важно знать, дошёл ли бот, через секунду-другую прочитайте
его положение (`list_room_users`) и при неудаче попробуйте другую точку рядом.

### `sit_on`

```python
async def sit_on(self, anchor: AnchorPosition) -> None
```

Посадить бота на место предмета мебели. Идентификатор предмета и номер места
(`entity_id`, `anchor_ix`) берите из положения человека, который на этой мебели сидит: у
сидящего `location` — это `AnchorPosition`.

```python
from sukarisebot import AnchorPosition, Bot, Location, User


class Follower(Bot):
    async def on_user_move(self, user: User, position: Location) -> None:
        if isinstance(position, AnchorPosition):
            await self.api.sit_on(position)
```

`ResponseError` — места нет или оно занято. В 3D-мире бот сначала идёт к месту: если мир не
посадил его за 8 секунд, это отказ «The bot could not reach that seat», и бот стоит там, где стоял.

### `teleport_user`

```python
async def teleport_user(self, user_id: str, position: Position) -> None
```

Мгновенно переместить человека в точку на полу. **Нужны права модератора** в комнате —
права только дизайнера недостаточно. Бот подчиняется тем же правилам, что и
модератор-человек.

## Комната и права

### `list_room_users`

```python
async def list_room_users(self) -> list[RoomUser]
```

Кто сейчас в комнате и где стоит или сидит. Обычно вызывать вручную не нужно: состав
ведёт [`bot.room`](tools.md#состав-комнаты-botroom). Возвращает список `RoomUser`
(`.user`, `.location`).

### `privileges`

```python
async def privileges(self, user_id: str) -> RoomPermissions
```

Права человека в этой комнате: `.moderator`, `.designer`. `None` в поле означает, что
сервер не сообщил.

```python
permissions = await self.api.privileges(user.id)
if permissions.moderator:
    ...
```

### `set_privileges`

```python
async def set_privileges(
    self,
    user_id: str,
    *,
    moderator: bool | None = None,
    designer: bool | None = None,
) -> None
```

Выдать или отобрать права модератора и дизайнера (`None` — не менять).

> **На сервере SukaRise ботам менять права нельзя**: это могут только владелец комнаты и
> персонал. Вызов всегда заканчивается `ResponseError`. Метод оставлен для совместимости
> с кодом, написанным под официальный SDK Highrise.

## Модерация

Для модерации у бота должны быть **права модератора** в комнате: право «дизайнер»,
достаточное для входа, не подходит. Бот подчиняется тем же правилам, что человек:
нельзя наказать владельца комнаты, а модератора может наказать только владелец.
Действия доступны только в 2D-комнатах.

### `moderate`

```python
async def moderate(self, user_id: str, action: ModerationAction, *, seconds: int | None = None) -> None
```

Выгнать, заблокировать, разблокировать или заглушить.

| Параметр | Описание |
|---|---|
| `user_id` | к кому применить |
| `action` | `"kick"`, `"ban"`, `"unban"` или `"mute"` |
| `seconds` | срок блокировки или заглушки, от 0 до 2 592 000 (30 суток); `None` — срок не задан, решает сервер |

`InvalidArgument` — неизвестное действие или срок вне диапазона. `ResponseError` — нет
прав модератора или цель защищена. Ниже — короткие формы.

### `kick`

```python
async def kick(self, user_id: str) -> None
```

Выгнать из комнаты. То же, что `moderate(user_id, "kick")`.

### `ban`

```python
async def ban(self, user_id: str, *, seconds: int | None = None) -> None
```

Заблокировать. То же, что `moderate(user_id, "ban", seconds=seconds)`.

### `unban`

```python
async def unban(self, user_id: str) -> None
```

Снять блокировку или заглушку. То же, что `moderate(user_id, "unban")`.

### `mute`

```python
async def mute(self, user_id: str, seconds: int) -> None
```

Заглушить на срок: человек не сможет писать в чат. То же, что
`moderate(user_id, "mute", seconds=seconds)`.

```python
from sukarisebot import Bot, ResponseError, User


class Guard(Bot):
    async def on_chat(self, user: User, message: str) -> None:
        if "спам" in message.lower():
            try:
                await self.api.mute(user.id, 60)
            except ResponseError:
                await self.api.chat("Не могу заглушить: у меня нет прав модератора.")
```

## Чаевые и покупки

### `tip`

```python
async def tip(self, user_id: str, gold_bar: GoldBar) -> bool
```

Дать человеку в комнате чаевые слитком золота **из кошелька бота**. Возвращает `True`,
если чаевые отправлены, и `False`, если у бота не хватает золота (это ответ, а не
ошибка; ничего не списывается). Отправитель платит чуть больше, чем получает адресат:
например, 11 золота за `gold_bar_10`.

Допустимые слитки (`GoldBar`): `gold_bar_1`, `gold_bar_5`, `gold_bar_10`, `gold_bar_50`,
`gold_bar_100`, `gold_bar_500`, `gold_bar_1k`, `gold_bar_5000`, `gold_bar_10k`; число —
сколько золота получит адресат. Адресат должен быть в комнате. Только 2D.

```python
paid = await self.api.tip(user.id, "gold_bar_10")
if not paid:
    await self.api.chat("Золота не хватает :(")
```

### `buy_item`

```python
async def buy_item(self, item_id: str) -> bool
```

Купить предмет в магазине **за золото бота**. Ботам продаются только предметы, которые
магазин продаёт за золото. Возвращает `True` — куплено, `False` — не хватило золота.
Купленное появляется в [`inventory`](#inventory).

## Личные сообщения

Личные сообщения — это диалоги вне комнаты. Человек пишет боту через обычный интерфейс
игры; запрос на диалог принимается за бота сразу. Бот **отвечает** в диалогах, где он уже
есть, и не начинает их сам. Бот участвует только в личных диалогах (не в группах), а
отправляет только текст. Схема: [`on_message`](handlers.md#on_message) сообщает о
новом сообщении → [`messages`](#messages) читает → [`send_message`](#send_message)
отвечает.

### `conversations`

```python
async def conversations(self, *, not_joined: bool = False, last_id: str | None = None) -> ConversationPage
```

Личные диалоги бота, по 20 за раз. Для следующей страницы передайте в `last_id`
идентификатор последнего диалога текущей. `not_joined=True` показывает ещё не принятые
запросы; так как запросы принимаются за бота сразу, обычно их нет.

### `messages`

```python
async def messages(self, conversation_id: str, *, last_message_id: str | None = None) -> list[DirectMessage]
```

Сообщения диалога, **новые первыми**, по 20 за раз. Чтение новейшей страницы отмечает
диалог прочитанным. Чтобы пойти в прошлое, передайте идентификатор самого старого из
имеющихся сообщений в `last_message_id`.

### `send_message`

```python
async def send_message(self, conversation_id: str, content: str) -> None
```

Ответить в диалоге. Текст длиннее **1000 символов** режется на несколько сообщений.

### `send_bulk_message`

```python
async def send_bulk_message(self, user_ids: Sequence[str], content: str) -> None
```

Написать **до 100** людям сразу, но только тем, с кем у бота уже есть диалог (кто
ему писал). Остальным сообщение не уходит; если оно не дошло ни до кого — отказ. Текст не
длиннее 1000 символов (здесь он не режется).

### `leave_conversation`

```python
async def leave_conversation(self, conversation_id: str) -> None
```

Выйти из диалога.

## Кошелёк, гардероб и инвентарь

### `wallet`

```python
async def wallet(self) -> list[CurrencyItem]
```

Все валюты бота. Золото — элемент с `type == "gold"`.

### `gold`

```python
async def gold(self) -> int
```

Золото бота (0, если золота нет). Удобная обёртка над `wallet()`. Золото бот получает
чаевыми; владелец забирает его себе в личном кабинете, на карточке бота.

### `outfit_of`

```python
async def outfit_of(self, user_id: str) -> list[Item]
```

Во что сейчас одет человек (или сам бот). Свой наряд бот может узнать и через
`await self.my_outfit()`.

### `inventory`

```python
async def inventory(self) -> list[Item]
```

Одежда, которой владеет бот.

### `wear`

```python
async def wear(self, items: Sequence[Item]) -> None
```

Заменить наряд бота целиком. Перед отправкой SDK проверяет наряд ([`outfit_problems`](tools.md#наряд-outfit_problems-и-category_of)): тело закрыто, части
тела на месте, каждая базовая категория встречается один раз. Затем наряд проверяет
сервер. Пока у владельца бота активный PREMIUM, смена наряда **бесплатна**: бот может надеть любую
вещь каталога, покупать её не нужно. Владелец может написать боту `myoutfit` в чат или
шёпотом, и бот наденет *текущий наряд владельца*.

`InvalidArgument` — наряд нарушает правила (причины перечислены в тексте). `ResponseError` —
нет PREMIUM у владельца или в наряде есть вещь, которой нет в каталоге.

```python
from sukarisebot import Bot, Context, command


class Mirror(Bot):
    @command("copyme", description="надеть мой наряд")
    async def copyme(self, ctx: Context) -> None:
        outfit = await ctx.api.outfit_of(ctx.user.id)
        await ctx.api.wear(outfit)
        await ctx.reply("Готово!")
```

## Вспомогательная функция

### `split_message`

```python
def split_message(text: str, limit: int = 500) -> list[str]
```

Разрезает текст на куски не длиннее `limit` символов, по возможности по пробелам; пробелы
на стыках отбрасываются. Если в пределах `limit` нет пробела, слово режется ровно по
`limit`. Так же `chat` и `send_message` делят длинный текст. Вызывать её вручную нужно,
только если вы хотите отправить части с паузами или в разные места.
