[English](../en/handlers.md) | [Русский](../ru/handlers.md) | **Português (Brasil)**

# Manipuladores de eventos

Um manipulador é um método da classe do bot no formato `async def on_...`. Todos eles são
definidos em `Bot` e **não fazem nada por padrão**, então você sobrescreve só os que precisa.

```python
from sukarisebot import Bot, Location, User


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Hello, {user.username}!")
```

Regras comuns a todos os manipuladores:

- O método precisa ser `async def`. Pegue a assinatura na tabela abaixo; no PyCharm ela é gerada,
  junto com a descrição, por **Code → Override Methods** (`Ctrl+O`).
- O SDK inscreve o bot **apenas nos eventos que têm um manipulador sobrescrito**, além do chat e
  da entrada e saída de pessoas (os comandos e o `bot.room` precisam deles). Não chega tráfego
  sobrando. Mais em [Como o SDK funciona](architecture.md#assinaturas-de-eventos).
- Os eventos são tratados **um de cada vez, na ordem de chegada**. Enquanto um manipulador não
  termina, o próximo evento espera. Leve o trabalho demorado para tarefas.
- Uma exceção dentro de um manipulador não para o bot: ela é passada ao `on_error`.
- A assinatura não pode ser alterada: o SDK chama os manipuladores com argumentos posicionais na
  ordem indicada aqui.

## Tabela-resumo

| Manipulador | Quando é chamado | Evento | Assinatura | Em 3D |
|---|---|---|---|---|
| [`on_start(session)`](#on_start) | o bot entrou na sala; de novo após cada reconexão | `SessionMetadata` | — | sim |
| [`on_chat(user, message)`](#on_chat) | uma fala no chat público | `ChatEvent` | `chat` | sim |
| [`on_whisper(user, message)`](#on_whisper) | um sussurro dirigido ao bot | `ChatEvent` | `chat` | sim |
| [`on_emote(user, emote_id, receiver)`](#on_emote) | alguém executou um emote | `EmoteEvent` | `emote` | sim |
| [`on_reaction(user, reaction, receiver)`](#on_reaction) | um jogador enviou uma reação a outro | `ReactionEvent` | `reaction` | não |
| [`on_user_join(user, position)`](#on_user_join) | alguém entrou na sala | `UserJoinedEvent` | `user_joined` | sim |
| [`on_user_leave(user)`](#on_user_leave) | alguém saiu | `UserLeftEvent` | `user_left` | sim |
| [`on_user_move(user, position)`](#on_user_move) | alguém andou ou sentou (em 3D: andou) | `UserMovedEvent` | `user_moved` | sim |
| [`on_channel(sender_id, message, tags)`](#on_channel) | uma mensagem oculta de outro bot | `ChannelEvent` | `channel` | sim |
| [`on_moderate(moderator_id, target_user_id, moderation_type, duration)`](#on_moderate) | moderação na sala | `ModerationEvent` | `moderation` | sim |
| [`on_tip(sender, receiver, item)`](#on_tip) | uma gorjeta na sala | `TipEvent` | `tip_reaction` | sim |
| [`on_message(user_id, conversation_id, is_new_conversation)`](#on_message) | uma pessoa escreveu uma mensagem direta ao bot | `MessageEvent` | `message` | sim |
| [`on_error(error, event)`](#on_error) | um manipulador, comando ou temporizador falhou | — | — | — |

As assinaturas `chat`, `user_joined` e `user_left` estão sempre ligadas (as duas últimas, exceto
no modo "sala limpa"): sem o chat os comandos não funcionam, e sem entradas e saídas não
funciona o `bot.room`.

Em uma sala 3D o bot recebe os eventos marcados com "sim" na última coluna: chat e sussurros,
entrada e saída de pessoas, caminhadas e emotes das pessoas, moderação, mensagens ocultas de
outros bots e mensagens diretas. As reações das pessoas não chegam ao bot em 3D: o cliente 3D
não as envia. As gorjetas das pessoas chegam também em 3D. O bot descobre a posição das pessoas
pelos eventos de caminhada e pela requisição `list_room_users()` (ou `await self.refresh_room()`).

## Cada manipulador em detalhe

### `on_start`

```python
async def on_start(self, session: SessionMetadata) -> None
```

O bot entrou na sala. É chamado **após cada (re)conexão**, então escreva-o de modo que uma
chamada repetida não faça mal (por exemplo, não inicie laços infinitos aqui). A essa altura o
`bot.room` já está preenchido (a menos que o modo "sala limpa" esteja ligado). Um bom lugar para
uma saudação e para a configuração inicial.

- `session`: quem é o bot (`session.user_id`), em que sala está
  (`session.room_info.room_name`, `.owner_id`) e quais limites de frequência valem.

### `on_chat`

```python
async def on_chat(self, user: User, message: str) -> None
```

Uma fala no chat público da sala. É chamado para qualquer fala, inclusive para mensagens de
comando (`!roll`): o comando executa separadamente, depois deste manipulador. O servidor não
envia ao bot as falas dele mesmo em uma sala 2D, e o SDK não executa comandos escritos pelo
próprio bot.

### `on_whisper`

```python
async def on_whisper(self, user: User, message: str) -> None
```

Um sussurro dirigido ao bot (na sala). O bot não vê os sussurros que as outras pessoas trocam
entre si. Não confunda com as mensagens diretas em conversas: essas chegam em
[`on_message`](#on_message).

### `on_emote`

```python
async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None
```

Alguém executou um emote. `receiver` é a pessoa a quem ele se dirige, ou `None` se não se dirige
a ninguém.

### `on_reaction`

```python
async def on_reaction(self, user: User, reaction: str, receiver: User) -> None
```

Um jogador enviou a outro uma reação: `clap`, `heart`, `thumbs`, `wave` ou `wink`. O parâmetro
`reaction` é uma string comum (não um `Literal`): assim o código não quebra se o servidor um dia
acrescentar uma reação nova.

### `on_user_join`

```python
async def on_user_join(self, user: User, position: Location) -> None
```

Um usuário entrou na sala. `position` é onde ele apareceu: uma `Position` (um ponto no chão) ou
uma `AnchorPosition` (um assento em um móvel).

### `on_user_leave`

```python
async def on_user_leave(self, user: User) -> None
```

Um usuário saiu da sala.

### `on_user_move`

```python
async def on_user_move(self, user: User, position: Location) -> None
```

Um usuário andou até outro ponto ou sentou. Em uma sala movimentada esses eventos são
frequentes; inscreva-se só se precisar deles.

### `on_channel`

```python
async def on_channel(self, sender_id: str, message: str, tags: tuple[str, ...]) -> None
```

Uma mensagem oculta de outro bot nesta sala (veja [`BotAPI.channel`](api.md#channel)). Os
jogadores não veem essas mensagens. O bot não recebe as próprias mensagens.

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

Uma ação de moderação foi executada na sala: `moderation_type` é `kick`, `ban`, `unban` ou
`mute`; `duration` é o prazo em segundos ou `None`. O bot não é avisado das ações que ele mesmo
executou. Se o próprio bot for punido, `target_user_id` é igual a `bot.session.user_id`.

### `on_tip`

```python
async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None
```

Alguém deu uma gorjeta a alguém. **O evento chega para qualquer gorjeta na sala**, e não só para
as do bot. Uma gorjeta para o próprio bot é aquela em que `receiver.id == self.session.user_id`.

`item` é um `CurrencyItem` (ouro: `item.amount` é quanto ouro o destinatário recebeu) ou um
`Item` (um objeto). Uma gorjeta ao bot sempre chega **em ouro**: o valor da barra é creditado na
carteira do bot (`gold_bar_10` dá 10 de ouro). O dono retira o ouro acumulado no painel pessoal.
Para um exemplo veja [`examples/tipping_bot.py`](../../examples/tipping_bot.py).

```python
from sukarisebot import Bot, CurrencyItem, Item, User


class Thanks(Bot):
    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        if self.session is None or receiver.id != self.session.user_id:
            return  # not a tip for the bot
        if isinstance(item, CurrencyItem):
            await self.api.chat(f"Thank you, {sender.username}, for {item.amount} gold!")
```

### `on_message`

```python
async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None
```

Uma pessoa escreveu ao bot uma **mensagem direta** (em uma conversa fora da sala). O evento não
traz o texto: leia-o com `await self.api.messages(conversation_id)` (mensagens mais novas
primeiro) e responda com `await self.api.send_message(conversation_id, "…")`.

- O pedido de conversa é aceito pelo bot automaticamente.
- O bot não escreve primeiro em uma conversa: quem começa é a pessoa.
- O bot participa apenas de conversas diretas (não de grupos).

```python
from sukarisebot import Bot


class Echo(Bot):
    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        messages = await self.api.messages(conversation_id)
        if messages and messages[0].sender_id == user_id:
            await self.api.send_message(conversation_id, f"You wrote: {messages[0].content}")
```

### `on_error`

```python
async def on_error(self, error: Exception, event: Event | None) -> None
```

Um manipulador, comando ou temporizador lançou uma exceção. Por padrão o erro é escrito no log
`sukarisebot` junto com o traceback. Sobrescreva o método para, por exemplo, avisar o dono:

```python
from sukarisebot import Bot, Event


class Careful(Bot):
    async def on_error(self, error: Exception, event: Event | None) -> None:
        await super().on_error(error, event)  # keep the log entry
        if self.owner_id is not None and self.owner_id in self.room:
            await self.api.whisper(self.owner_id, f"Error: {error}")
```

`event` é o evento durante o tratamento do qual o erro ocorreu. Para um comando é o evento de
chat que o chamou; `None` para um temporizador e para um erro em `on_start`. Se o próprio
`on_error` falhar, isso vai para o log e o bot continua funcionando.

## Qual evento vai para qual manipulador

O chat é dividido entre dois manipuladores: o mesmo `ChatEvent` vai para `on_chat` se
`whisper=False` e para `on_whisper` se `whisper=True`. Os demais eventos se ligam aos
manipuladores um a um. Em todos os casos os comandos (`@command`) executam **depois** do
manipulador do evento de chat.

## O que fazer com um evento que não tem manipulador

Nada: se um manipulador não é sobrescrito, o SDK não se inscreve nesse evento e ele não chega
(exceto o chat e as entradas e saídas, que sempre chegam). Isso vale também para o
[`wait_for`](commands.md#diálogos-wait_for): o chat é sempre entregue (a assinatura dele fica
ligada por causa dos comandos), e para esperar qualquer outro evento, sobrescreva o manipulador
dele: um vazio basta (`async def on_emote(...): pass`), senão não há assinatura e o `wait_for`
não receberá o evento.
