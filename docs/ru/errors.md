[English](../en/errors.md) | **Русский** | [Português (Brasil)](../pt-BR/errors.md)

# Ошибки и отказы

В этой странице — все исключения SDK, что они означают и что с ними делать, а также
таблица отказов, которые присылает сервер: при подключении и при отдельных запросах.

> **Язык сообщений.** Тексты исключений SDK — русские. Тексты отказов, которые присылает
> сервер (`error.message`), — английские, как в официальном протоколе. Ниже у каждого
> из них есть перевод и совет.

## Иерархия исключений

Все ошибки SDK наследуют `SukaRiseError`, поэтому `except SukaRiseError` ловит их все.

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

| Исключение | Атрибуты | Когда возникает | Что делать |
|---|---|---|---|
| `InvalidArgument` | — | пустой текст, неизвестная реакция/слиток/действие, координата вне ±1000, номер места вне 0…255, слишком длинный идентификатор или метка, наряд нарушает правила, неверное имя команды. **Запрос не отправлялся.** | Исправить вызов в своём коде. Это ошибка программиста, а не сбой связи. |
| `ResponseError` | `message` | Сервер отказал в запросе: нет прав, человека нет в комнате, действие не поддерживается сервером. Соединение при этом работает. | Прочитать `error.message`, при необходимости ответить игроку. Таблица ниже. |
| `RateLimited` | `message` | Сервер отказал из-за лимита частоты, и несколько повторов SDK не помогли. Запрос **не выполнялся**. Наследует `ResponseError`. | Реже слать запросы; повторить позже. Подробнее — в разделе «Лимит частоты» ниже. |
| `RequestTimeout` | — | Сервер не ответил за 10 секунд. Запрос мог выполниться. | Если действие нельзя повторять вслепую (чаевые, покупка), сначала проверьте результат (`await api.gold()`). |
| `NotConnected` | — | `bot.api` вне работающего бота; запрос во время переподключения; обрыв посреди запроса. | Дождаться подключения; в таймерах проверять `self.connected`. |
| `ConnectionRefused` | `message`, `do_not_reconnect` | Сервер не принял подключение или оборвал сессию. Выходит из `run`/`start`. | Таблица «Отказы при подключении» ниже. |
| `ProtocolError` | — | Сервер прислал непонятный кадр. Одиночный кадр SDK пропускает и пишет в журнал. | Обычно ничего: сообщите о проблеме, если повторяется. |

## Как обработать

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

Если исключение не поймано, оно не роняет бота: SDK передаёт его в
[`on_error`](handlers.md#on_error), и бот продолжает работу.

## Лимит частоты

Сервер ограничивает частоту запросов по категориям, и SDK ведёт такие же счётчики, поэтому
почти всегда сам ждёт своей очереди. Но задержки сети могут сжать интервалы между запросами,
и сервер на долю секунды раньше SDK решит, что бюджет исчерпан. Тогда он отвечает отказом
`Rate limit exceeded for <category> requests` **до** выполнения запроса. Раньше такой отказ
сразу превращался в `ResponseError`. Теперь SDK повторяет запрос до трёх раз с паузой в
секунду (безопасно: запрос не выполнялся) и только после этого выбрасывает `RateLimited`.
Исключение наследует `ResponseError`, поэтому прежний `except ResponseError` продолжает
работать.

## Отказы при подключении

Исключение `ConnectionRefused` выходит из `run()`/`start()`, когда бот остановился и
дальше работать не может. Столбец «SDK» говорит, что делает SDK:

- **повторяет** — слово сервера «отказ временный» (`do_not_reconnect = False`): бот с
  `reconnect=True` не завершается, а пробует снова с растущей паузой до 30 секунд;
- **завершается** — отказ окончательный (`do_not_reconnect = True`): `run()` выбрасывает
  `ConnectionRefused`.

С `reconnect=False` исключение выбрасывается в обоих случаях, в том числе при временном
HTTP-отказе (например, 503); различить их можно по `error.do_not_reconnect`.

| Текст сервера | Что значит | Что делать | SDK |
|---|---|---|---|
| `invalid or revoked bot token` | Токен неверен, заменён кнопкой «Новый токен», бот выключен или удалён, либо владелец заблокирован. | Проверьте токен; при необходимости выпустите новый в кабинете. | завершается |
| `the bot's owner needs an active PREMIUM subscription` | У владельца бота нет активной подписки PREMIUM. | Продлите PREMIUM; бот подключится сам. | повторяет |
| `the bot needs designer rights in the room: add the bot's username as a designer in the room settings` | Бот не добавлен в дизайнеры комнаты. | Добавьте логин бота в дизайнеры комнаты. | завершается |
| `the room does not exist` | Комнаты с таким ID нет. | Проверьте `room_id`. | завершается |
| `the room is full` | В комнате нет места. | Освободите место или выберите другую комнату. | завершается |
| `the room already holds the maximum number of bots` | В комнате уже три бота. | Отключите одного из ботов. | завершается |
| `bots cannot join this 3D room: the 3D world service is not available to bots on this server` | Эта 3D-комната недоступна ботам на сервере. | Используйте 2D-комнату. | завершается |
| `bots are not enabled on this server` | Бот-API на сервере выключен. | Обратитесь к администратору сервера. | завершается |
| `A valid room-id header is required` | `room_id` пуст или содержит недопустимые символы. | Проверьте `room_id`. | завершается |
| `This bot connected from another place` | Тот же токен подключили в другом месте; побеждает новое подключение. | Запускайте одного бота с одним токеном. | завершается |
| `the room is not ready, try again shortly` | Комната ещё не готова (например, 3D-мир запускается). | Ничего: SDK повторит. | повторяет |
| `The room could not be joined right now` | Временная ошибка входа. | Ничего: SDK повторит. | повторяет |
| `Authentication is temporarily unavailable` | Временная ошибка проверки токена. | Ничего: SDK повторит. | повторяет |
| `The server is restarting` | Сервер перезапускается. | Ничего: SDK повторит. | повторяет |
| HTTP 404 | Нет такого адреса: неверный `SUKARISEBOT_URL` или бот-API не подключён к веб-серверу. Пока сервер обновляется, маршрут может ненадолго пропасть, поэтому SDK повторяет попытки, но не дольше 5 минут подряд. | Проверьте адрес. | повторяет, потом завершается |
| HTTP 400, 401, 403 | Запрос отклонён на уровне HTTP. | Проверьте адрес и токен. | завершается |
| HTTP 503 `too many bot connections` | Шлюз перегружен подключениями. | Ничего: SDK повторит. | повторяет |

Кроме того, SDK повторяет подключение при обрыве сети и при любых других временных
HTTP-ответах.

## Отказы отдельных запросов (`ResponseError`)

Типичные тексты, которые бот может увидеть в `error.message`:

| Текст сервера | Что значит и что делать |
|---|---|
| `Rate limit exceeded for <category> requests` | Превышен лимит частоты. SDK ждёт очереди сам и сам повторяет такой отказ; наружу он выходит как `RateLimited`. |
| `The message is empty` / `The message is longer than 500 characters` | Пустая или слишком длинная реплика (SDK режет длинные сам). |
| `That user is not in this room` / `That user does not exist` | Адресата шёпота, реакции или чаевых нет в комнате. |
| `The bot is muted in this room` / `The bot is banned from this room` | Бота заглушили или заблокировали. |
| `The bot cannot whisper this user` / `The whisper could not be sent` / `This user is not accepting whispers from the bot` | Шёпот не доставлен. |
| `The bot cannot walk there` / `The destination is not on the floor of this room` / `The destination is not a point in the room` | Точка для `move_to` или `teleport_user` недоступна. |
| `That seat is not in this room` | Места для `sit_on` нет. |
| `Teleporting a user needs moderator rights in the room` | Для телепорта нужны права модератора. |
| `That seat is taken` | Место занято человеком или другим ботом. Выберите другое. |
| `The bot is already sitting` | Бот уже сидит. Сначала встаньте, пойдя куда-нибудь (`move_to`). |
| `The bot could not reach that seat` | В 3D-мире бот не дошёл до места за 8 секунд и остался стоять. Выберите другое место или точку ближе. |
| `The bot sat on another seat, and that one is not reachable` | В 3D-мире мир посадил бота на другое место, а выбранное недостижимо. Бот теперь сидит на другом месте. |
| `That user was moved a moment ago` | В 3D-мире человека можно переместить не чаще раза в 0,6 с. Повторите через секунду. |
| `The bot is not in this room` / `The bot is no longer in the room` | Бот ещё не вошёл в комнату или уже вышел из неё. Дождитесь входа. |
| `The emote is unknown` / `The bot cannot perform that emote` | Такой эмоции нет или бот не может её сыграть (платная — без PREMIUM у владельца). |
| `This emote needs a partner, and a bot cannot give one yet` | Парные эмоции ботам недоступны. |
| `Unknown reaction` | Неизвестная реакция. |
| `That gold bar is not available` / `That user cannot be tipped` / `The recipient cannot hold more` / `Tips are unavailable right now` | Чаевые не отправлены. Нехватка золота — не отказ: `tip` возвращает `False`. |
| `That item does not exist` / `That item is not sold to bots` / `That item is not available right now` / `That item is only for players with SukaRise PREMIUM` / `Bots can buy only items sold for gold` / `The bot cannot hold more items` / `The shop is unavailable right now` | Покупка невозможна. Нехватка золота — не отказ: `buy_item` возвращает `False`. |
| `The bot's owner needs an active PREMIUM subscription to change the bot's outfit` | Без PREMIUM у владельца смена наряда запрещена. |
| `Unknown item: …` / `The outfit is empty` / `The outfit has too many items` / `The outfit has an item without an id` / `The outfit is missing a … item` / `The outfit wears two … items; a bot wears one of each basic part` / `The outfit does not cover the body…` | Наряд не прошёл проверку сервера. |
| `Bots cannot change room privileges; the room owner does that` / `Changing room privileges from bots is not available yet` | `set_privileges` всегда отказывает: права в комнате меняют только владелец и персонал. |
| `The conversation does not exist` / `Bots take part in direct conversations only` / `The bot cannot write to this conversation` | Диалога нет, он не личный или бот не может в него писать. |
| `The bot has no open conversation with these users: bots answer people who wrote first` | `send_bulk_message`: бот пишет только тем, кто уже писал ему. |
| `This request is not supported on this server` | Эта операция сервером не поддерживается. |
| `Internal error` | Внутренняя ошибка сервера. |

Некоторые действия **всегда** отказывают ботам на SukaRise: `set_privileges`, голосовой
чат, рюкзак, платные услуги комнаты, перенос людей в другую комнату, медиа-сообщения.
SDK не предоставляет для них методов, кроме `set_privileges`.

## Журнал

SDK пишет в журнал с именем `sukarisebot`. Чтобы видеть переподключения, отказы и
ошибки в обработчиках, включите вывод:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
```

Уровни: `INFO` — переподключения; `WARNING` — потеря соединения, временные отказы, отброшенные
кадры и события; `ERROR` — исключения в вашем коде (трассировка). Токен в журнал
не попадает.
