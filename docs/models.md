# Модели данных

Все данные, которые SDK передаёт вашему коду, — **неизменяемые dataclass'ы**
(`frozen=True`, `slots=True`). Их нельзя изменить после создания, поэтому их безопасно
хранить, сравнивать (`==`) и использовать как ключи словаря. Названия полей совпадают с
официальным SDK Highrise, поэтому код, написанный под тот SDK, читается так же.

Все классы импортируются из пакета: `from sukarisebot import User, Position, ChatEvent`.

## Допустимые значения (литералы)

Редактор подсказывает эти значения, а анализатор типов (mypy, pyright) ловит опечатки.
Рядом с каждым литералом есть множество с теми же значениями для проверок во время работы.

| Тип | Значения | Множество |
|---|---|---|
| `Facing` | `"FrontRight"`, `"FrontLeft"`, `"BackRight"`, `"BackLeft"` | `FACINGS` |
| `Reaction` | `"clap"`, `"heart"`, `"thumbs"`, `"wave"`, `"wink"` | `REACTIONS` |
| `GoldBar` | `"gold_bar_1"`, `"gold_bar_5"`, `"gold_bar_10"`, `"gold_bar_50"`, `"gold_bar_100"`, `"gold_bar_500"`, `"gold_bar_1k"`, `"gold_bar_5000"`, `"gold_bar_10k"` | `GOLD_BARS` |
| `ModerationAction` | `"kick"`, `"ban"`, `"unban"`, `"mute"` | `MODERATION_ACTIONS` |

## Люди и места

### `User`

Пользователь SukaRise: игрок или другой бот.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `str` | постоянный идентификатор аккаунта; не меняется при смене имени |
| `username` | `str` | имя в игре на момент события |

Сравнивайте людей по `id`, а не по `username`: имя можно сменить.

### `Position`

Точка на полу комнаты и направление взгляда.

| Поле | Тип | Описание |
|---|---|---|
| `x` | `float` | координата по оси X |
| `y` | `float` | высота над полом; для обычного пола `0.0` |
| `z` | `float` | координата по оси Z |
| `facing` | `Facing` | куда смотрит персонаж; по умолчанию `"FrontRight"` |

Допустимы конечные числа в пределах ±1000.

### `AnchorPosition`

Место для сидения на предмете мебели.

| Поле | Тип | Описание |
|---|---|---|
| `entity_id` | `str` | идентификатор предмета мебели в комнате |
| `anchor_ix` | `int` | номер места на этом предмете, от 0 до 255 |

### `Location`

`Location = Position | AnchorPosition` — **где находится пользователь**: стоит на полу или
сидит на мебели. Различайте варианты через `isinstance` или `match`:

```python
from sukarisebot import AnchorPosition, Location, Position


def describe(location: Location) -> str:
    match location:
        case Position(x=x, z=z):
            return f"стоит в точке ({x:.1f}, {z:.1f})"
        case AnchorPosition(entity_id=furniture, anchor_ix=place):
            return f"сидит на {furniture}, место {place}"
```

### `RoomUser`

Человек (или бот) в комнате. Элементы `list_room_users()` и `bot.room.users()`.

| Поле | Тип | Описание |
|---|---|---|
| `user` | `User` | кто это |
| `location` | `Location` | где он находится |

### `RoomInfo`

Сведения о комнате бота.

| Поле | Тип | Описание |
|---|---|---|
| `owner_id` | `str` | идентификатор владельца комнаты |
| `room_name` | `str` | название комнаты |

### `RoomPermissions`

Права пользователя в комнате.

| Поле | Тип | Описание |
|---|---|---|
| `moderator` | `bool \| None` | может ли модерировать; `None` — сервер не сообщил |
| `designer` | `bool \| None` | может ли редактировать комнату; `None` — сервер не сообщил |

## Вещи и деньги

### `CurrencyItem`

Сумма в одной валюте: строка кошелька или чаевые золотом.

| Поле | Тип | Описание |
|---|---|---|
| `type` | `str` | название валюты; золото — `"gold"` |
| `amount` | `int` | количество |

### `Item`

Предмет: часть одежды в гардеробе или наряде.

| Поле | Тип | Описание |
|---|---|---|
| `type` | `str` | вид предмета; для одежды `"clothing"` |
| `amount` | `int` | количество; для одежды 1 |
| `id` | `str` | идентификатор предмета в каталоге, например `shirt-n_plaid_blackwhite` |
| `account_bound` | `bool` | предмет привязан к аккаунту и не передаётся другим (по умолчанию `False`) |
| `active_palette` | `int \| None` | номер выбранной палитры цветов или `None` |

## События

События приходят в обработчики [`on_...`](handlers.md). Все они объединены в тип
`Event` — `ChatEvent | EmoteEvent | ReactionEvent | UserJoinedEvent | UserLeftEvent |
UserMovedEvent | ChannelEvent | ModerationEvent | TipEvent | MessageEvent`. Он нужен для
подсказок типов (`wait_for`, `on_error`) и для разбора через `match`.

| Класс | Поля | Какой обработчик |
|---|---|---|
| `ChatEvent` | `user: User`, `message: str`, `whisper: bool` | `on_chat` / `on_whisper` |
| `EmoteEvent` | `user: User`, `emote_id: str`, `receiver: User \| None` | `on_emote` |
| `ReactionEvent` | `user: User`, `reaction: str`, `receiver: User` | `on_reaction` |
| `UserJoinedEvent` | `user: User`, `position: Location` | `on_user_join` |
| `UserLeftEvent` | `user: User` | `on_user_leave` |
| `UserMovedEvent` | `user: User`, `position: Location` | `on_user_move` |
| `ChannelEvent` | `sender_id: str`, `message: str`, `tags: tuple[str, ...]` | `on_channel` |
| `ModerationEvent` | `moderator_id: str`, `target_user_id: str`, `moderation_type: str`, `duration: int \| None` | `on_moderate` |
| `TipEvent` | `sender: User`, `receiver: User`, `item: Item \| CurrencyItem` | `on_tip` |
| `MessageEvent` | `user_id: str`, `conversation_id: str`, `is_new_conversation: bool` | `on_message` |

Примечания:

- `ReactionEvent.reaction` и `ModerationEvent.moderation_type` — обычные строки, а не
  литералы: так SDK не ломается, если сервер добавит новое значение.
- `TipEvent.item` — `CurrencyItem` для золота и `Item` для предмета. Боту чаевые всегда
  приходят золотом.
- `ModerationEvent.duration` — срок в секундах; `None`, если срок не задан.
- `MessageEvent` не несёт текста: сообщение читается через `api.messages(conversation_id)`.

## Личные сообщения

### `DirectMessage`

Одно сообщение личного диалога.

| Поле | Тип | Описание |
|---|---|---|
| `message_id` | `str` | идентификатор сообщения; годится для постраничного чтения назад |
| `conversation_id` | `str` | диалог, к которому относится сообщение |
| `created_at` | `str \| None` | время отправки в том виде, в каком его прислал сервер |
| `content` | `str` | текст сообщения |
| `sender_id` | `str` | идентификатор отправителя |
| `category` | `str` | вид сообщения: `text` или `invite` (приглашение) |

### `Conversation`

Личный диалог бота. Боты участвуют только в личных диалогах.

| Поле | Тип | Описание |
|---|---|---|
| `id` | `str` | идентификатор диалога |
| `did_join` | `bool` | принял ли бот диалог (запросы принимаются за бота сразу) |
| `unread_count` | `int` | сколько сообщений бот ещё не прочитал |
| `last_message` | `DirectMessage \| None` | последнее сообщение |
| `muted` | `bool` | отключены ли уведомления диалога |
| `member_ids` | `tuple[str, ...]` | идентификаторы участников |
| `owner_id` | `str \| None` | создатель диалога |

### `ConversationPage`

Страница диалогов бота — до 20 штук.

| Поле | Тип | Описание |
|---|---|---|
| `conversations` | `tuple[Conversation, ...]` | диалоги страницы |
| `not_joined` | `int` | сколько запросов на диалог бот ещё не принял; обычно 0 |

## Сессия и лимиты

### `SessionMetadata`

Первый кадр принятого подключения. Приходит в `on_start` и доступен как `bot.session`.

| Поле | Тип | Описание |
|---|---|---|
| `user_id` | `str` | идентификатор аккаунта самого бота |
| `room_info` | `RoomInfo` | комната, в которую бот вошёл |
| `rate_limits` | `dict[str, RateLimit]` | лимиты частоты по категориям |
| `connection_id` | `str` | идентификатор этого подключения (для журналов) |

### `RateLimit`

Лимит частоты для одной категории: не больше `requests` запросов за `seconds` секунд.

| Поле | Тип | Описание |
|---|---|---|
| `requests` | `int` | сколько запросов разрешено |
| `seconds` | `float` | за какое окно времени |

## Постоянные значения

Кроме типов, пакет экспортирует константы, которыми пользуются сам SDK и ваши проверки:
`FACINGS`, `REACTIONS`, `GOLD_BARS`, `MODERATION_ACTIONS` (множества допустимых
значений), `DEFAULT_URL` (адрес шлюза по умолчанию) и `ENV_TOKEN`, `ENV_ROOM_ID`,
`ENV_URL` (названия переменных окружения).
