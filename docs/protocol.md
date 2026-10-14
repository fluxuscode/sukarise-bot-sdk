# Протокол

Эта страница описывает, что именно SDK отправляет по сети. Она нужна, чтобы понять,
как устроены запросы бота, отлаживать связь или написать клиента на другом языке. Для
обычной работы с SDK читать её не обязательно.

Протокол совместим с официальным Python SDK Highrise: кадры тегируются полем `_type`,
запросы нумеруются полем `rid`. Код и боты, рассчитанные на тот протокол, работают с
тем же форматом; отличается только адрес.

## Подключение

Бот открывает **websocket** по адресу шлюза (по умолчанию `wss://sukarise.ru/web/botapi`,
переопределяется аргументом `url` или переменной `SUKARISEBOT_URL`). Метод — `GET` с
обновлением до websocket.

| Что | Где | Значение |
|---|---|---|
| Токен бота | заголовок `api-token` | `srbot_…` из личного кабинета |
| Комната | заголовок `room-id` | идентификатор комнаты, не длиннее 128 символов |
| Подписки | параметр адреса `events` | например `?events=chat,user_joined` |

Допустимые названия подписок: `chat`, `emote`, `reaction`, `user_joined`, `user_left`,
`user_moved`, `channel`, `moderation`, `tip_reaction`, `message`, `voice`. SDK подбирает их
по переопределённым обработчикам (см. [«Устройство SDK»](architecture.md#подписки-на-события)).
Если подписки не указаны, сервер присылает все события.

Если подключение отклонено, сервер присылает кадр `Error` (см. ниже) или отвечает
HTTP-ошибкой до обновления до websocket.

## Кадры

Каждый кадр — JSON-объект с обязательным полем `_type`:

```json
{"_type": "ChatRequest", "rid": "7", "message": "Привет", "whisper_target_id": null}
```

- **Первый кадр сервера** — всегда `SessionMetadata` (или `Error`, если бот не принят).
- **Запрос** бота несёт `rid` — строку с номером запроса. Номера нарастают с 1.
- **Ответ** сервера повторяет `rid` запроса. Тип ответа получается заменой `Request` на
  `Response` (`ChatRequest` → `ChatResponse`). Ответ пуст, если запрос ничего не
  возвращает.
- **Событие** — кадр без `rid`: сервер присылает его сам.
- **Ошибка** — кадр `Error` с текстом `message`. Если у него есть `rid`, это отказ
  конкретному запросу (`ResponseError`). Если `rid` нет, это сообщение о соединении:
  с признаком `do_not_reconnect: true` соединение закончено окончательно.
- **Keepalive** — `{"_type": "KeepaliveRequest"}` без `rid`, раз в 20 секунд. Сервер отвечает
  `KeepaliveResponse`; SDK его игнорирует. Keepalive не входит в лимиты.

Размер кадра: сервер принимает кадры до 64 КиБ, SDK принимает до 256 КиБ.

### `SessionMetadata`

```json
{
  "_type": "SessionMetadata",
  "user_id": "…",
  "room_info": {"owner_id": "…", "room_name": "…"},
  "rate_limits": {"chat": [20, 10], "info": [30, 10]},
  "connection_id": "…",
  "sdk_version": null
}
```

`rate_limits` — «категория → [запросов, секунд]». Разбирается в `SessionMetadata`
(см. [модели](models.md#sessionmetadata)).

### `Error`

```json
{"_type": "Error", "message": "the room is full", "do_not_reconnect": true}
```

Поле `do_not_reconnect` необязательно: без него отказ временный. С `rid` — отказ запросу:
`{"_type": "Error", "message": "The message is empty", "rid": "7"}`.

## Запросы

Таблица соответствует методам [`BotAPI`](api.md). «Лимит» — категория
частоты.

| Метод | Тип запроса | Лимит | Поля запроса | Ответ |
|---|---|---|---|---|
| `chat` | `ChatRequest` | `chat` | `message`, `whisper_target_id: null` | `ChatResponse` |
| `whisper` | `ChatRequest` | `chat` | `message`, `whisper_target_id` | `ChatResponse` |
| `channel` | `ChannelRequest` | `channel` | `message`, `tags`, `only_to` | `ChannelResponse` |
| `emote` | `EmoteRequest` | `emote` | `emote_id`, `target_user_id` | `EmoteResponse` |
| `react` | `ReactionRequest` | `emote` | `reaction`, `target_user_id` | `ReactionResponse` |
| `move_to` | `FloorHitRequest` | `move` | `destination` (`x`, `y`, `z`, `facing`) | `FloorHitResponse` |
| `sit_on` | `AnchorHitRequest` | `move` | `anchor` (`entity_id`, `anchor_ix`) | `AnchorHitResponse` |
| `teleport_user` | `TeleportRequest` | `teleport` | `user_id`, `destination` | `TeleportResponse` |
| `list_room_users` | `GetRoomUsersRequest` | `info` | — | `GetRoomUsersResponse` (`content`: пары «пользователь, положение») |
| `privileges` | `GetRoomPrivilegeRequest` | `info` | `user_id` | `GetRoomPrivilegeResponse` (`content`: `moderator`, `designer`) |
| `set_privileges` | `ChangeRoomPrivilegeRequest` | `moderate` | `user_id`, `permissions` (`moderator`, `designer`) | `ChangeRoomPrivilegeResponse` (на SukaRise — всегда отказ) |
| `moderate`, `kick`, `ban`, `unban`, `mute` | `ModerateRoomRequest` | `moderate` | `user_id`, `moderation_action`, `action_length` | `ModerateRoomResponse` |
| `tip` | `TipUserRequest` | `tip` | `user_id`, `gold_bar` | `TipUserResponse` (`result`: `success` или `insufficient_funds`) |
| `buy_item` | `BuyItemRequest` | `shop` | `item_id` | `BuyItemResponse` (`result`) |
| `conversations` | `GetConversationsRequest` | `info` | `not_joined`, `last_id` | `GetConversationsResponse` (`conversations`, `not_joined`) |
| `messages` | `GetMessagesRequest` | `info` | `conversation_id`, `last_message_id` | `GetMessagesResponse` (`messages`) |
| `send_message` | `SendMessageRequest` | `message` | `conversation_id`, `content`, `type: "text"` | `SendMessageResponse` |
| `send_bulk_message` | `SendBulkMessageRequest` | `message` | `user_ids`, `content`, `type: "text"` | `SendBulkMessageResponse` |
| `leave_conversation` | `LeaveConversationRequest` | `message` | `conversation_id` | `LeaveConversationResponse` |
| `wallet`, `gold` | `GetWalletRequest` | `info` | — | `GetWalletResponse` (`content`: `type`, `amount`) |
| `outfit_of` | `GetUserOutfitRequest` | `info` | `user_id` | `GetUserOutfitResponse` (`outfit`) |
| `inventory` | `GetInventoryRequest` | `info` | — | `GetInventoryResponse` (`items`) |
| `wear` | `SetOutfitRequest` | `info` | `outfit` (предметы) | `SetOutfitResponse` |

Положение (`destination`, `position`) — объект `{"x": 1.0, "y": 0.0, "z": 2.0, "facing":
"FrontRight"}`; место на мебели — `{"entity_id": "…", "anchor_ix": 0}`. Предмет —
`{"type": "clothing", "amount": 1, "id": "…", "account_bound": false, "active_palette": null}`.

## События

| Тип кадра | Подписка | Поля | Класс SDK |
|---|---|---|---|
| `ChatEvent` | `chat` | `user`, `message`, `whisper` | `ChatEvent` |
| `EmoteEvent` | `emote` | `user`, `emote_id`, `receiver` | `EmoteEvent` |
| `ReactionEvent` | `reaction` | `user`, `reaction`, `receiver` | `ReactionEvent` |
| `UserJoinedEvent` | `user_joined` | `user`, `position` | `UserJoinedEvent` |
| `UserLeftEvent` | `user_left` | `user` | `UserLeftEvent` |
| `UserMovedEvent` | `user_moved` | `user`, `position` | `UserMovedEvent` |
| `ChannelEvent` | `channel` | `sender_id`, `msg`, `tags` | `ChannelEvent` |
| `RoomModeratedEvent` | `moderation` | `moderatorId`, `targetUserId`, `moderationType`, `duration` | `ModerationEvent` |
| `TipReactionEvent` | `tip_reaction` | `sender`, `receiver`, `item` | `TipEvent` |
| `MessageEvent` | `message` | `user_id`, `conversation_id`, `is_new_conversation` | `MessageEvent` |

Пользователь в событии — `{"id": "…", "username": "…"}`. В `TipReactionEvent.item` золото —
`{"type": "gold", "amount": 10}`, предмет — полный объект предмета с `id`; SDK
различает их по наличию `id`. Нестандартные названия полей (`msg`, `moderatorId`)
унаследованы от официального протокола.

Кадры неизвестных типов SDK пропускает: новые события сервера не ломают старых ботов.
Кадр известного типа с неверными полями отбрасывается с предупреждением в журнале.

## Лимиты

Сервер ведёт для каждого соединения по «ведру» на категорию и отвечает отказом
`Rate limit exceeded for <категория> requests`, если оно пусто. SDK ведёт такие же
«вёдра» по значениям из `SessionMetadata.rate_limits` и ждёт сам, поэтому до отказа
обычно не доходит. Подробнее — в [«Устройстве SDK»](architecture.md#лимиты-частоты).

Дополнительные ограничения шлюза: реплика чата — до 500 символов; личное
сообщение — до 1000; сообщение канала — до 1024 байт, до 10 меток по 32 символа и до 50 адресатов;
координаты — в пределах ±1000; срок модерации — до 30 суток; запрос с неподдерживаемым
`type` сообщения — отказ (бот отправляет только `text`). Бот, отстающий
настолько, что очередь отправки шлюза переполняется, отключается.

## Одно соединение — один бот в одной комнате

Если бот подключается, пока старое соединение с тем же токеном ещё открыто, побеждает
новое: старое получает `Error` с `do_not_reconnect: true`. Бот может одновременно
находиться только в одной комнате, а в одной комнате может быть не больше трёх ботов.
