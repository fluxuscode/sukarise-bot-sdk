[English](../en/protocol.md) | [Русский](../ru/protocol.md) | **Português (Brasil)**

# Protocolo

Esta página descreve exatamente o que o SDK envia pela rede. Você precisa dela para entender
como as requisições de um bot são montadas, para depurar a conexão ou para escrever um cliente
em outra linguagem. Para o trabalho comum com o SDK não é obrigatório lê-la.

O protocolo é compatível com o SDK Python oficial do Highrise: os quadros são marcados com o
campo `_type` e as requisições são numeradas com o campo `rid`. Códigos e bots feitos para esse
protocolo funcionam com o mesmo formato; só o endereço é diferente.

## Conexão

O bot abre um **websocket** no endereço do gateway (por padrão
`wss://production-portal-refb.sukarise.ru/web/botapi`, substituído pelo argumento `url` ou pela
variável `SUKARISEBOT_URL`). O método é `GET` com atualização para websocket.

| O quê | Onde | Valor |
|---|---|---|
| O token do bot | o cabeçalho `api-token` | `srbot_…` do painel pessoal |
| A sala | o cabeçalho `room-id` | o identificador da sala, no máximo 128 bytes |
| Assinaturas | o parâmetro `events` do endereço | por exemplo `?events=chat,user_joined` |

Os nomes de assinatura permitidos: `chat`, `emote`, `reaction`, `user_joined`, `user_left`,
`user_moved`, `channel`, `moderation`, `tip_reaction`, `message`, `voice`. O SDK os escolhe pelos
manipuladores sobrescritos (veja [Como o SDK funciona](architecture.md#assinaturas-de-eventos)).
Se nenhuma assinatura for informada, o servidor envia todos os eventos.

Se a conexão for recusada, o servidor envia um quadro `Error` (veja abaixo) ou responde com um
erro HTTP antes da atualização para websocket.

## Quadros

Cada quadro é um objeto JSON com o campo obrigatório `_type`:

```json
{"_type": "ChatRequest", "rid": "7", "message": "Hello", "whisper_target_id": null}
```

- **O primeiro quadro do servidor** é sempre `SessionMetadata` (ou `Error`, se o bot não for
  aceito).
- **Uma requisição** do bot leva `rid`: uma string com o número da requisição. Os números
  crescem a partir de 1.
- **Uma resposta** do servidor repete o `rid` da requisição. O tipo da resposta se obtém
  trocando `Request` por `Response` (`ChatRequest` → `ChatResponse`). A resposta é vazia se a
  requisição não retorna nada.
- **Um evento** é um quadro sem `rid`: o servidor o envia por conta própria.
- **Um erro** é um quadro `Error` com o texto `message`. Se tiver `rid`, é a recusa de uma
  requisição específica (`ResponseError`). Se não tiver `rid`, é uma mensagem sobre a conexão:
  com o sinal `do_not_reconnect: true` a conexão terminou de vez.
- **Keepalive** é `{"_type": "KeepaliveRequest"}` sem `rid`, a cada 20 segundos. O servidor
  responde com `KeepaliveResponse`; o SDK o toma como sinal de que a conexão está viva. O
  keepalive não conta nos limites. Se nenhum quadro chegar do servidor por mais de três
  intervalos de keepalive, o SDK considera a conexão perdida e conecta de novo.

Tamanho do quadro: o servidor aceita quadros de até 64 KiB, o SDK aceita até 256 KiB.

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

`rate_limits` é "categoria → [requisições, segundos]". É lido para dentro de `SessionMetadata`
(veja [os modelos](models.md#sessionmetadata)).

### `Error`

```json
{"_type": "Error", "message": "the room is full", "do_not_reconnect": true}
```

O campo `do_not_reconnect` é opcional: sem ele a recusa é temporária. Com um `rid` é a recusa de
uma requisição: `{"_type": "Error", "message": "The message is empty", "rid": "7"}`.

## Requisições

A tabela corresponde aos métodos da [`BotAPI`](api.md). "Limite" é a categoria de frequência.

| Método | Tipo da requisição | Limite | Campos da requisição | Resposta |
|---|---|---|---|---|
| `chat` | `ChatRequest` | `chat` | `message`, `whisper_target_id: null` | `ChatResponse` |
| `whisper` | `ChatRequest` | `chat` | `message`, `whisper_target_id` | `ChatResponse` |
| `channel` | `ChannelRequest` | `channel` | `message`, `tags`, `only_to` | `ChannelResponse` |
| `emote` | `EmoteRequest` | `emote` | `emote_id`, `target_user_id` | `EmoteResponse` |
| `react` | `ReactionRequest` | `emote` | `reaction`, `target_user_id` | `ReactionResponse` |
| `move_to` | `FloorHitRequest` | `move` | `destination` (`x`, `y`, `z`, `facing`) | `FloorHitResponse` |
| `sit_on` | `AnchorHitRequest` | `move` | `anchor` (`entity_id`, `anchor_ix`) | `AnchorHitResponse` |
| `teleport_user` | `TeleportRequest` | `teleport` | `user_id`, `destination` | `TeleportResponse` |
| `list_room_users` | `GetRoomUsersRequest` | `info` | — | `GetRoomUsersResponse` (`content`: pares "usuário, posição") |
| `privileges` | `GetRoomPrivilegeRequest` | `info` | `user_id` | `GetRoomPrivilegeResponse` (`content`: `moderator`, `designer`) |
| `set_privileges` | `ChangeRoomPrivilegeRequest` | `moderate` | `user_id`, `permissions` (`moderator`, `designer`) | `ChangeRoomPrivilegeResponse` (sempre uma recusa no SukaRise) |
| `moderate`, `kick`, `ban`, `unban`, `mute` | `ModerateRoomRequest` | `moderate` | `user_id`, `moderation_action`, `action_length` | `ModerateRoomResponse` |
| `tip` | `TipUserRequest` | `tip` | `user_id`, `gold_bar` | `TipUserResponse` (`result`: `success` ou `insufficient_funds`) |
| `buy_item` | `BuyItemRequest` | `shop` | `item_id` | `BuyItemResponse` (`result`) |
| `conversations` | `GetConversationsRequest` | `info` | `not_joined`, `last_id` | `GetConversationsResponse` (`conversations`, `not_joined`) |
| `messages` | `GetMessagesRequest` | `info` | `conversation_id`, `last_message_id` | `GetMessagesResponse` (`messages`) |
| `send_message` | `SendMessageRequest` | `message` | `conversation_id`, `content`, `type: "text"` | `SendMessageResponse` |
| `send_bulk_message` | `SendBulkMessageRequest` | `message` | `user_ids`, `content`, `type: "text"` | `SendBulkMessageResponse` |
| `leave_conversation` | `LeaveConversationRequest` | `message` | `conversation_id` | `LeaveConversationResponse` |
| `wallet`, `gold` | `GetWalletRequest` | `info` | — | `GetWalletResponse` (`content`: `type`, `amount`) |
| `outfit_of` | `GetUserOutfitRequest` | `info` | `user_id` | `GetUserOutfitResponse` (`outfit`) |
| `inventory` | `GetInventoryRequest` | `info` | — | `GetInventoryResponse` (`items`) |
| `wear` | `SetOutfitRequest` | `info` | `outfit` (itens) | `SetOutfitResponse` |

Uma posição (`destination`, `position`) é um objeto `{"x": 1.0, "y": 0.0, "z": 2.0, "facing":
"FrontRight"}`; um assento em um móvel é `{"entity_id": "…", "anchor_ix": 0}`. Um item é
`{"type": "clothing", "amount": 1, "id": "…", "account_bound": false, "active_palette": null}`.

## Eventos

| Tipo do quadro | Assinatura | Campos | Classe do SDK |
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

Um usuário em um evento é `{"id": "…", "username": "…"}`. Em `TipReactionEvent.item` o ouro é
`{"type": "gold", "amount": 10}` e um objeto é um item completo com um `id`; o SDK os distingue
pela presença de `id`. Os nomes de campo fora do padrão (`msg`, `moderatorId`) são herdados do
protocolo oficial.

O SDK ignora quadros de tipos desconhecidos: eventos novos do servidor não quebram bots antigos.
Um quadro de tipo conhecido com campos errados é descartado com um aviso no log.

## Limites

Para cada conexão o servidor mantém um "balde" por categoria e responde com a recusa
`Rate limit exceeded for <category> requests` se ele estiver vazio. O SDK mantém os mesmos
"baldes" a partir dos valores de `SessionMetadata.rate_limits` e espera sozinho, então em geral
não se chega a uma recusa; se ela acontecer (atrasos de rede comprimiram os intervalos), o SDK
repete a requisição até três vezes: ela não foi executada. Mais em
[Como o SDK funciona](architecture.md#limites-de-frequência).

Limites adicionais do gateway: uma fala de chat tem até 500 caracteres; uma mensagem direta até
1000; uma mensagem de canal até 1024 bytes, até 10 etiquetas de 32 bytes e até 50 destinatários;
um identificador de emote até 96 bytes, um identificador de móvel em `sit_on` até 128 (o número
do assento é 0…255), um identificador de item em `buy_item` até 256, um identificador de conversa
até 128; uma roupa tem de 1 a 64 itens; as coordenadas ficam dentro de ±1000; o prazo de uma ação
de moderação é de até 30 dias; uma requisição com um `type` de mensagem não suportado é recusada
(o bot envia apenas `text`). Um bot que fica tão atrasado que a fila de envio do gateway estoura
é desconectado.

## Uma conexão: um bot em uma sala

Se um bot se conecta enquanto uma conexão antiga com o mesmo token ainda está aberta, a nova
vence: a antiga recebe um `Error` com `do_not_reconnect: true`. Um bot só pode estar em uma sala
por vez, e uma sala comporta no máximo três bots.
