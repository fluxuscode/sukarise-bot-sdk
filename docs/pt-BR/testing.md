[English](../en/testing.md) | [Русский](../ru/testing.md) | **Português (Brasil)**

# Testes sem servidor

O `Harness` executa um bot **em memória**: não há rede, não é preciso esperar os temporizadores,
e a sala é imitada com respostas preparadas. Você entrega eventos ao bot (`say`, `join`, `emit`)
e depois verifica o que o bot tentou fazer (`chats`, `whispers`, `requests`).

```python
import asyncio

from sukarisebot import Bot, Location, User
from sukarisebot.testing import Harness


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Welcome, {user.username}!")


def test_greeting() -> None:
    async def scenario() -> None:
        harness = Harness(Greeter())
        await harness.start()
        await harness.join("alice")
        assert harness.chats == ["Welcome, alice!"]

    asyncio.run(scenario())
```

Os testes executam com o `pytest` comum. Não são necessários plugins extras para testes
assíncronos: o cenário é envolvido em `asyncio.run(...)`.

## Como funciona

O `Harness` conecta o bot não a um servidor, mas a um "servidor que grava": o
`RecordingRequester`. Todas as ações do bot (`self.api.chat(...)` e outras) não vão para a rede,
mas são gravadas na lista `harness.requester.sent`. Os eventos que você entrega seguem o mesmo
caminho de uma conexão real: primeiro disparam as esperas do `wait_for`, depois os manipuladores
`on_...` e os comandos.

## Entregando eventos

| Método | O que faz |
|---|---|
| `await harness.start()` | "Conecta" o bot: chama `on_start`, carrega a lista da sala (exceto em "sala limpa") |
| `await harness.say(username, text, whisper=False)` | um usuário escreve no chat (ou sussurra ao bot) |
| `await harness.join(username, position)` | um usuário entra: vai para a lista da sala e chega um `UserJoinedEvent` |
| `await harness.leave(user)` | um usuário sai |
| `await harness.emit(event)` | entrega qualquer evento: `EmoteEvent`, `ModerationEvent`, `MessageEvent` e assim por diante |
| `harness.event_tip(sender, receiver, item)` | monta um `TipEvent` para entregar por `emit` |

O identificador de um usuário em um teste é `"user-" + username`. Cada chamada retorna quando o
bot terminou de tratar o evento.

## Verificando o resultado

| Membro | O que retorna |
|---|---|
| `harness.chats` | as falas do bot no chat público, em ordem |
| `harness.whispers` | os sussurros do bot, em ordem |
| `harness.requests("ModerateRoomRequest")` | todas as requisições de um tipo (`Sent`) |
| `harness.requester.sent` | todas as requisições em ordem |
| `harness.bot` | o próprio bot: verifique `bot.room`, `bot.state` e assim por diante |

`Sent` é o registro de uma requisição: `kind` (por exemplo, `"ChatRequest"`), `category` (o
limite) e `body` (os campos). Quais requisições cada método envia está em
[Protocolo](protocol.md).

```python
import asyncio

from sukarisebot import Bot, Context, command
from sukarisebot.testing import Harness


class Guard(Bot):
    @command("kick", owner_only=True)
    async def kick(self, ctx: Context) -> None:
        name = ctx.arg(0)
        entry = None if name is None else self.room.find(name)
        if entry is not None:
            await self.api.kick(entry.user.id)


def test_kick_asks_the_server_to_kick() -> None:
    async def scenario() -> None:
        harness = Harness(Guard(), owner_id="user-boss")
        await harness.start()
        await harness.join("mallory")
        await harness.say("boss", "!kick mallory")
        (request,) = harness.requests("ModerateRoomRequest")
        assert request.body["user_id"] == "user-mallory"
        assert request.body["moderation_action"] == "kick"

    asyncio.run(scenario())
```

Aqui `owner_id="user-boss"` faz do usuário `boss` o dono da sala (o identificador dele no teste é
`user-boss`).

## Configurando o "servidor"

O que o "servidor sabe" são os campos de `harness.requester`:

| Campo | O que define |
|---|---|
| `room` | a lista da sala (preenchida por `harness.join`) |
| `gold` | o ouro na carteira do bot |
| `inventory` | o guarda-roupa do bot |
| `permissions` | os direitos que `privileges` retorna |
| `tips_paid` | `False`: gorjetas e compras respondem "ouro insuficiente" |
| `conversation_frames`, `message_frames` | os quadros das conversas diretas e das mensagens |
| `refuse_with` | qualquer requisição é recusada com um `ResponseError` com este texto |

```python
import asyncio

from sukarisebot import Bot, Context, ResponseError, command
from sukarisebot.testing import Harness


class Tipper(Bot):
    @command("tipme")
    async def tipme(self, ctx: Context) -> None:
        if await self.api.tip(ctx.user.id, "gold_bar_10"):
            await ctx.reply("Here you go!")
        else:
            await ctx.reply("Not enough gold.")


def test_a_poor_bot_says_so() -> None:
    async def scenario() -> None:
        harness = Harness(Tipper())
        harness.requester.tips_paid = False
        await harness.start()
        await harness.say("alice", "!tipme")
        assert harness.chats == ["Not enough gold."]

    asyncio.run(scenario())


def test_a_refused_request_raises() -> None:
    async def scenario() -> None:
        harness = Harness(Tipper())
        harness.requester.refuse_with = "That user is not in this room"
        await harness.start()
        try:
            await harness.bot.api.chat("hi")
        except ResponseError as error:
            assert "not in this room" in error.message

    asyncio.run(scenario())
```

## Gorjetas e mensagens diretas

```python
import asyncio

from sukarisebot import Bot, CurrencyItem, Item, MessageEvent, User
from sukarisebot.testing import Harness


class Cashier(Bot):
    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        if self.session is not None and receiver.id == self.session.user_id and isinstance(item, CurrencyItem):
            await self.api.chat(f"+{item.amount}")

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        messages = await self.api.messages(conversation_id)
        if messages:
            await self.api.send_message(conversation_id, messages[0].content.upper())


def test_tips_and_direct_messages() -> None:
    async def scenario() -> None:
        harness = Harness(Cashier(), bot_id="bot-1")
        harness.requester.message_frames = [
            {
                "message_id": "m1",
                "conversation_id": "c1",
                "createdAt": None,
                "content": "hello",
                "sender_id": "user-ann",
                "category": "text",
            }
        ]
        await harness.start()
        ann = User("user-ann", "ann")
        await harness.emit(harness.event_tip(ann, User("bot-1", "bot"), CurrencyItem("gold", 10)))
        await harness.emit(MessageEvent("user-ann", "c1", True))
        assert harness.chats == ["+10"]
        (reply,) = harness.requests("SendMessageRequest")
        assert reply.body["content"] == "HELLO"

    asyncio.run(scenario())
```

## Diálogos com `wait_for`

Um comando que espera uma resposta não termina até a resposta chegar. Por isso, em um teste,
execute-o como uma tarefa separada, deixe-o começar a esperar, entregue a resposta e aguarde a
tarefa:

```python
import asyncio

from sukarisebot import Bot, ChatEvent, Context, command
from sukarisebot.testing import Harness


class Asker(Bot):
    @command("ask")
    async def ask(self, ctx: Context) -> None:
        answer = await self.wait_for(
            ChatEvent,
            lambda event: event.whisper and event.user.id == ctx.user.id,
            timeout=5,
        )
        await ctx.reply(f"You answered: {answer.message}")


def test_a_dialog() -> None:
    async def scenario() -> None:
        harness = Harness(Asker())
        await harness.start()
        task = asyncio.create_task(harness.say("alice", "!ask"))
        await asyncio.sleep(0)  # let the command reach wait_for
        await harness.say("alice", "42", whisper=True)
        await task
        assert harness.chats == ["You answered: 42"]

    asyncio.run(scenario())
```

## Temporizadores

O Harness **não executa** os temporizadores `@every`: não há motivo para esperá-los em um teste.
Verifique o método diretamente:

```python
import asyncio

from sukarisebot import Bot, every
from sukarisebot.testing import Harness


class Herald(Bot):
    @every(300)
    async def announce(self) -> None:
        await self.api.chat("Room rules: be polite.")


def test_the_announcement() -> None:
    async def scenario() -> None:
        bot = Herald()
        harness = Harness(bot)
        await harness.start()
        await bot.announce()
        assert harness.chats == ["Room rules: be polite."]

    asyncio.run(scenario())
```

## O que o Harness não faz

- Não verifica as **regras do servidor**: direitos de moderador, se a pessoa está na sala, os
  limites de ouro. Imite essas recusas com os campos `refuse_with` e `tips_paid`.
- Não filtra eventos por assinaturas: o `emit` aceita qualquer evento, mesmo que o bot não tenha
  o manipulador correspondente (então ele simplesmente não chama nada).
- Não aplica limites de frequência e não usa a rede.
- Não verifica o protocolo. Disso se encarrega um conjunto separado de testes do próprio SDK em
  um websocket de verdade (o diretório `tests/` do repositório, `fake_gateway.py`).

Antes de executar um bot em um servidor de verdade, é prático testá-lo uma vez em uma sala de
testes.
