[English](../en/tools.md) | **Русский** | [Português (Brasil)](../pt-BR/tools.md)

# Инструменты

Вспомогательные части SDK: состав комнаты, режим «чистой комнаты», хранилище данных,
HTTP-клиент, проверка наряда и запуск из командной строки.

## Состав комнаты (`bot.room`)

`bot.room` (класс `Room`) отвечает на вопрос «кто сейчас в комнате и где он». Объект
**только для чтения**: заполняет его сам SDK.

| Член | Что делает |
|---|---|
| `room.users()` | список `RoomUser` — все, кто сейчас в комнате |
| `room.get(user_id)` | запись человека по идентификатору или `None` |
| `room.find("@Alice")` | запись по имени; регистр и ведущий `@` не важны; `None`, если нет |
| `user_id in room` | есть ли человек в комнате |
| `len(room)` | сколько людей в комнате |
| `room.seeded` | `True`, если в составе все, кто в комнате, а не только увиденные входящими |

```python
from sukarisebot import Bot, Context, command


class Finder(Bot):
    @command("where", description="where a player is: !where name")
    async def where(self, ctx: Context) -> None:
        name = ctx.arg(0)
        entry = None if name is None else self.room.find(name)
        if entry is None:
            await ctx.reply("I do not see that player.")
        else:
            await ctx.reply(f"{entry.user.username}: {entry.location}")
```

### Что обновляет состав

При подключении SDK загружает состав с сервера (`await bot.refresh_room()` вызывается
сам). Дальше состав обновляют **события**. Входы и выходы людей SDK получает всегда
(кроме режима «чистой комнаты»), поэтому список людей остаётся верным без всяких
обработчиков. А вот перемещения приходят боту, только если для них переопределён обработчик
(см. [«Подписки на события»](architecture.md#подписки-на-события)): чтобы `bot.room` знал,
где кто стоит и сидит, переопределите `on_user_move`. Тело обработчика может быть пустым:

```python
from sukarisebot import Bot, Location, User


class Tracker(Bot):
    """Keeps the positions in bot.room current and does nothing else."""

    async def on_user_move(self, user: User, position: Location) -> None:
        pass
```

Без `on_user_move` положение человека в составе — то, где он был при входе или при последней
загрузке. Обновить состав полностью можно в любой момент: `await self.refresh_room()` (один
запрос `info`). До версии 0.3.0 входы и выходы тоже обновляли состав, только если для них
переопределялись `on_user_join` и `on_user_leave`.

## Режим «чистой комнаты»

`start(clean_room=True)` (или `run(clean_room=True)`) — бот **не делает ни одного
запроса, которого не просил его код**. В частности, он не запрашивает список людей при
подключении, поэтому `bot.room` начинается пустым (`seeded == False`) и наполняется по
событиям входа. Полный список загружается явно: `await self.refresh_room()`. В этом режиме
SDK не подписывается и на входы-выходы людей, пока вы сами не переопределите их обработчики.

Режим нужен ботам, которые только слушают: они не создают лишнего трафика. Пример —
[`examples/clean_room.py`](../../examples/clean_room.py). Из командной строки:
`python -m sukarisebot module:Class --clean-room`.

## `JsonStore`: данные между запусками

`self.state` и `self.user_state()` живут только пока работает процесс. Для данных, которые
должны пережить перезапуск, есть `JsonStore` — небольшое хранилище «ключ → JSON-значение» в
одном файле.

```python
from pathlib import Path

from sukarisebot import Bot, Context, JsonStore, JsonValue, Location, User, command


def add_visit(old: JsonValue, username: str) -> JsonValue:
    record: dict[str, JsonValue] = dict(old) if isinstance(old, dict) else {}
    visits = record.get("visits", 0)
    record["visits"] = (visits if isinstance(visits, int) else 0) + 1
    record["username"] = username
    return record


class VisitCounter(Bot):
    def __init__(self, path: str | Path = "visits.json") -> None:
        super().__init__()  # required: otherwise the commands are not found
        self.store = JsonStore(path)

    async def on_user_join(self, user: User, position: Location) -> None:
        await self.store.update(user.id, lambda old: add_visit(old, user.username))

    @command("visits", description="how many times I have visited")
    async def visits(self, ctx: Context) -> None:
        record = await self.store.get(ctx.user.id)
        count = record.get("visits", 0) if isinstance(record, dict) else 0
        await ctx.reply(f"@{ctx.user.username}, you have visited {count} time(s).")
```

| Метод | Что делает |
|---|---|
| `await store.get(key, default=None)` | значение по ключу или `default` |
| `await store.set(key, value)` | записать значение |
| `await store.update(key, change, default=None)` | заменить значение результатом `change(старое)` и вернуть новое |
| `await store.all()` | копия всех записей (например, для таблицы лидеров) |
| `store.path` | путь к файлу |

Что нужно знать:

- **Ключ — идентификатор игрока (`user.id`), а не имя**: имя можно сменить.
- Значение — JSON-значение: `None`, `bool`, число, строка, список или словарь. Тип
  `JsonValue` описывает это для анализатора типов.
- **Запись атомарна**: данные пишутся во временный файл, который затем заменяет старый,
  поэтому сбой посреди записи не оставит наполовину записанный файл. Дисковые операции идут
  в рабочем потоке и не останавливают бота.
- **Одновременные изменения не теряются**: `set` и `update` выстраиваются в очередь.
  Для «прочитать, изменить, записать» используйте `update`, а не пару `get` + `set`.
- Если запись не удалась (например, значение нельзя записать в JSON), хранилище остаётся
  прежним.
- Файл читается целиком при первом обращении и держится в памяти; каждое изменение
  записывает его целиком. Подходит для небольших данных, но не для больших баз.
- Если файл существует, но в нём не JSON-объект, первое обращение выбросит `ValueError`.

## HTTP-клиент `bot.http`

Для запросов к другим сервисам (курсы валют, переводчик, ваша база) у бота есть общий
`aiohttp`-клиент `bot.http`. Он создаётся при первом обращении, закрывается сам при
остановке бота, и у каждого запроса таймаут 10 секунд.

```python
from sukarisebot import Bot, Context, command


class Rates(Bot):
    @command("rate", description="a currency rate: !rate USD")
    async def rate(self, ctx: Context) -> None:
        pair = ctx.arg(0) or "USD"
        # The address is made up: put your own service here.
        async with self.http.get("https://example.com/api/rate", params={"pair": pair}) as response:
            await ctx.reply(await response.text())
```

Используйте его вместо создания клиента в каждом обработчике.

## Наряд: `outfit_problems` и `category_of`

`api.wear(items)` сначала проверяет наряд на стороне SDK, чтобы вы получили понятный
`InvalidArgument` вместо отказа сервера. Ту же проверку можно вызвать самому:

```python
from sukarisebot import Item, outfit_problems

items = [Item(type="clothing", amount=1, id="shirt-n_plaid_blackwhite")]
for problem in outfit_problems(items):
    print(problem)
```

`outfit_problems(items)` возвращает список проблем (пустой — наряд верен). Проверяется:

- все предметы — одежда (`type == "clothing"`);
- ни один предмет не повторяется;
- каждая **базовая категория** (`shirt`, `pants`, `skirt`, `dress`, `fullsuit` и части тела)
  встречается не больше раза;
- на месте все части тела: `body-flesh`, `eye`, `eyebrow`, `nose`, `mouth`;
- тело закрыто: рубашка и брюки, рубашка и юбка, платье или комбинезон.

`category_of(item_id)` определяет базовую категорию по идентификатору предмета (он
начинается с названия категории) или возвращает `None` для аксессуаров.

Категорию SDK читает из идентификатора, а сервер — из типа предмета в каталоге. Поэтому
предметы с идентификаторами `bag-…`, под которыми бывает что угодно (бровь, рубашка, брюки),
SDK не классифицирует и не считает ошибкой то, что они способны восполнить: последние два
пункта списка выше проверяются, только если таких предметов не хватает, чтобы закрыть
недостающее. Раньше такие наряды, например скопированные у человека через `outfit_of`,
отклонялись ложно.

Владение вещами SDK не проверяет — его знает только сервер. Пока у владельца бота
активный PREMIUM, смена наряда бесплатна: бот может надеть любую вещь каталога.
Свой текущий наряд бот может узнать через `await bot.my_outfit()`.

## Запуск из командной строки

Бота можно запустить без собственного скрипта запуска — как официальной командой
`highrise`:

```bash
python -m sukarisebot examples.dice:Dice --room room-... --token srbot_...
sukarisebot examples.dice:Dice --clean-room
```

| Параметр | Описание |
|---|---|
| `module:Class` | бот в виде «имя модуля, двоеточие, имя класса»; модуль ищется в текущем каталоге и как обычным `import` |
| `--room ID` | идентификатор комнаты (или переменная `SUKARISEBOT_ROOM_ID`) |
| `--token TOKEN` | токен бота (или переменная `SUKARISEBOT_TOKEN`) |
| `--url URL` | адрес шлюза (или переменная `SUKARISEBOT_URL`) |
| `--clean-room` | режим «чистой комнаты» |
| `--log-level LEVEL` | `DEBUG`, `INFO` (по умолчанию), `WARNING` или `ERROR`; другое значение — ошибка использования |

Код завершения: `0` — штатно, `1` — сервер отказал (`ConnectionRefused` и др.), `2` —
бот не найден (модуль не импортируется или класс не наследует `Bot`). Бот создаётся
конструктором **без аргументов**.

Тот же поиск доступен из кода: `load_bot("module:Class")` возвращает готового бота.

## Низкоуровневые части

Для нестандартных задач из пакета экспортируются и внутренние классы:

- `Engine` — соединение: websocket, очередь событий, переподключение. Создаётся самим
  `Bot`; нужен, если вы хотите управлять подключением вручную.
- `Requester` — интерфейс «отправить запрос, получить ответ». Реализуют `Engine` и
  тестовый `RecordingRequester`. `BotAPI` зависит только от него.
- `Commands`, `Command`, `CommandSpec`, `CommandHandler` — реестр команд и его части.

Обычному боту они не нужны. Как они работают — в [«Устройстве SDK»](architecture.md) и
[«Протоколе»](protocol.md).
