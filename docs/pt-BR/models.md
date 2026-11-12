[English](../en/models.md) | [Русский](../ru/models.md) | **Português (Brasil)**

# Modelos de dados

Todos os dados que o SDK entrega ao seu código são **dataclasses imutáveis** (`frozen=True`,
`slots=True`). Não podem ser alterados depois de criados, então é seguro guardá-los, compará-los
(`==`) e usá-los como chaves de dicionário. Os nomes dos campos coincidem com o SDK oficial do
Highrise, então um código escrito para aquele SDK se lê do mesmo jeito.

Todas as classes são importadas do pacote: `from sukarisebot import User, Position, ChatEvent`.

## Valores permitidos (literais)

O editor sugere esses valores e um verificador de tipos (mypy, pyright) pega erros de digitação.
Ao lado de cada literal há um conjunto com os mesmos valores para verificações em tempo de
execução.

| Tipo | Valores | Conjunto |
|---|---|---|
| `Facing` | `"FrontRight"`, `"FrontLeft"`, `"BackRight"`, `"BackLeft"` | `FACINGS` |
| `Reaction` | `"clap"`, `"heart"`, `"thumbs"`, `"wave"`, `"wink"` | `REACTIONS` |
| `GoldBar` | `"gold_bar_1"`, `"gold_bar_5"`, `"gold_bar_10"`, `"gold_bar_50"`, `"gold_bar_100"`, `"gold_bar_500"`, `"gold_bar_1k"`, `"gold_bar_5000"`, `"gold_bar_10k"` | `GOLD_BARS` |
| `ModerationAction` | `"kick"`, `"ban"`, `"unban"`, `"mute"` | `MODERATION_ACTIONS` |

## Pessoas e lugares

### `User`

Um usuário do SukaRise: um jogador ou outro bot.

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | `str` | o identificador permanente da conta; não muda quando o nome muda |
| `username` | `str` | o nome no jogo no momento do evento |

Compare pessoas por `id`, e não por `username`: o nome pode ser trocado.

### `Position`

Um ponto no chão da sala e uma direção de olhar.

| Campo | Tipo | Descrição |
|---|---|---|
| `x` | `float` | a coordenada no eixo X |
| `y` | `float` | a altura acima do chão; `0.0` para um chão comum |
| `z` | `float` | a coordenada no eixo Z |
| `facing` | `Facing` | para onde o personagem olha; `"FrontRight"` por padrão |

São permitidos números finitos dentro de ±1000.

### `AnchorPosition`

Um assento em um móvel.

| Campo | Tipo | Descrição |
|---|---|---|
| `entity_id` | `str` | o identificador do móvel na sala |
| `anchor_ix` | `int` | o número do assento nesse móvel, de 0 a 255 |

### `Location`

`Location = Position | AnchorPosition` é **onde um usuário está**: de pé no chão ou sentado em um
móvel. Distinga as variantes com `isinstance` ou `match`:

```python
from sukarisebot import AnchorPosition, Location, Position


def describe(location: Location) -> str:
    match location:
        case Position(x=x, z=z):
            return f"standing at ({x:.1f}, {z:.1f})"
        case AnchorPosition(entity_id=furniture, anchor_ix=place):
            return f"sitting on {furniture}, seat {place}"
```

### `RoomUser`

Uma pessoa (ou um bot) na sala. Os elementos de `list_room_users()` e `bot.room.users()`.

| Campo | Tipo | Descrição |
|---|---|---|
| `user` | `User` | quem é |
| `location` | `Location` | onde está |

### `RoomInfo`

Informações sobre a sala do bot.

| Campo | Tipo | Descrição |
|---|---|---|
| `owner_id` | `str` | o identificador do dono da sala |
| `room_name` | `str` | o nome da sala |

### `RoomPermissions`

Os direitos de um usuário na sala.

| Campo | Tipo | Descrição |
|---|---|---|
| `moderator` | `bool \| None` | se pode moderar; `None`: o servidor não informou |
| `designer` | `bool \| None` | se pode editar a sala; `None`: o servidor não informou |

## Coisas e dinheiro

### `CurrencyItem`

Uma quantia em uma moeda: uma linha da carteira ou uma gorjeta em ouro.

| Campo | Tipo | Descrição |
|---|---|---|
| `type` | `str` | o nome da moeda; o ouro é `"gold"` |
| `amount` | `int` | a quantidade |

### `Item`

Um item: uma peça de roupa no guarda-roupa ou na roupa vestida.

| Campo | Tipo | Descrição |
|---|---|---|
| `type` | `str` | o tipo do item; `"clothing"` para roupas |
| `amount` | `int` | a quantidade; 1 para roupas |
| `id` | `str` | o identificador do item no catálogo, por exemplo `shirt-n_plaid_blackwhite` |
| `account_bound` | `bool` | o item é vinculado à conta e não é passado a outros (`False` por padrão) |
| `active_palette` | `int \| None` | o número da paleta de cores escolhida ou `None` |

## Eventos

Os eventos chegam aos manipuladores [`on_...`](handlers.md). Todos eles são reunidos no tipo
`Event`: `ChatEvent | EmoteEvent | ReactionEvent | UserJoinedEvent | UserLeftEvent |
UserMovedEvent | ChannelEvent | ModerationEvent | TipEvent | MessageEvent`. Ele serve para as
dicas de tipos (`wait_for`, `on_error`) e para desmontar eventos com `match`.

| Classe | Campos | Qual manipulador |
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

Observações:

- `ReactionEvent.reaction` e `ModerationEvent.moderation_type` são strings comuns, e não
  literais: assim o SDK não quebra se o servidor acrescentar um valor novo.
- `TipEvent.item` é um `CurrencyItem` para ouro e um `Item` para um objeto. Uma gorjeta a um bot
  sempre chega em ouro.
- `ModerationEvent.duration` é o prazo em segundos; `None` se nenhum prazo foi definido.
- `MessageEvent` não traz texto: a mensagem é lida com `api.messages(conversation_id)`.

## Mensagens diretas

### `DirectMessage`

Uma mensagem de uma conversa direta.

| Campo | Tipo | Descrição |
|---|---|---|
| `message_id` | `str` | o identificador da mensagem; serve para paginar para trás |
| `conversation_id` | `str` | a conversa a que a mensagem pertence |
| `created_at` | `str \| None` | o horário de envio na forma como o servidor o enviou |
| `content` | `str` | o texto da mensagem |
| `sender_id` | `str` | o identificador de quem enviou |
| `category` | `str` | o tipo de mensagem: `text` ou `invite` (um convite) |

### `Conversation`

Uma conversa direta do bot. Os bots participam apenas de conversas diretas.

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | `str` | o identificador da conversa |
| `did_join` | `bool` | se o bot aceitou a conversa (os pedidos são aceitos pelo bot na hora) |
| `unread_count` | `int` | quantas mensagens o bot ainda não leu |
| `last_message` | `DirectMessage \| None` | a última mensagem |
| `muted` | `bool` | se as notificações da conversa estão desligadas |
| `member_ids` | `tuple[str, ...]` | os identificadores dos participantes |
| `owner_id` | `str \| None` | o criador da conversa |

### `ConversationPage`

Uma página das conversas do bot: até 20.

| Campo | Tipo | Descrição |
|---|---|---|
| `conversations` | `tuple[Conversation, ...]` | as conversas da página |
| `not_joined` | `int` | quantos pedidos de conversa o bot ainda não aceitou; em geral 0 |

## Sessão e limites

### `SessionMetadata`

O primeiro quadro de uma conexão aceita. Chega em `on_start` e fica disponível como
`bot.session`.

| Campo | Tipo | Descrição |
|---|---|---|
| `user_id` | `str` | o identificador da conta do próprio bot |
| `room_info` | `RoomInfo` | a sala em que o bot entrou |
| `rate_limits` | `dict[str, RateLimit]` | os limites de frequência por categoria |
| `connection_id` | `str` | o identificador desta conexão (para os logs) |

### `RateLimit`

O limite de frequência de uma categoria: no máximo `requests` requisições em `seconds` segundos.

| Campo | Tipo | Descrição |
|---|---|---|
| `requests` | `int` | quantas requisições são permitidas |
| `seconds` | `float` | em que janela de tempo |

## Constantes

Além dos tipos, o pacote exporta constantes usadas pelo próprio SDK e pelas suas verificações:
`FACINGS`, `REACTIONS`, `GOLD_BARS`, `MODERATION_ACTIONS` (conjuntos de valores permitidos),
`DEFAULT_URL` (o endereço padrão do gateway) e `ENV_TOKEN`, `ENV_ROOM_ID`, `ENV_URL` (os nomes
das variáveis de ambiente).
