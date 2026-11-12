[English](../en/recipes.md) | [Русский](../ru/recipes.md) | **Português (Brasil)**

# Receitas

Soluções prontas para tarefas comuns. Cada receita é um bot completo; você pode salvá-lo em um
arquivo e executá-lo (`python -m sukarisebot module:Class`). Mais exemplos estão no diretório
[`examples/`](../../examples/).

## Uma saudação que lembra

Cumprimenta os novatos de um jeito diferente dos frequentadores. Lembra as visitas entre
execuções.

```python
from pathlib import Path

from sukarisebot import Bot, JsonStore, JsonValue, Location, User


def count_visit(old: JsonValue) -> JsonValue:
    visits = old if isinstance(old, int) else 0
    return visits + 1


class Host(Bot):
    def __init__(self, path: str | Path = "visits.json") -> None:
        super().__init__()
        self.store = JsonStore(path)

    async def on_user_join(self, user: User, position: Location) -> None:
        visits = await self.store.update(user.id, count_visit)
        if visits == 1:
            await self.api.chat(f"Welcome, {user.username}! Glad to see a new guest.")
        else:
            await self.api.chat(f"Welcome back, {user.username}! This is your visit number {visits}.")
```

## Agradecer uma gorjeta ao bot

Agradece só as **gorjetas ao bot** (e não as trocadas entre outras pessoas) e conta o ouro. O
ouro enviado ao bot vai para a carteira dele, e o dono o retira no painel pessoal.

```python
from sukarisebot import Bot, CurrencyItem, Item, User


class Thanks(Bot):
    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        if self.session is None or receiver.id != self.session.user_id:
            return  # not a tip for the bot
        if isinstance(item, CurrencyItem):
            total = await self.api.gold()
            await self.api.chat(f"Thank you, {sender.username}! I now have {total} gold.")
```

Uma versão mais completa, com ranking, é o [`examples/tipping_bot.py`](../../examples/tipping_bot.py).

## Respostas a mensagens diretas

Uma pessoa escreve ao bot em mensagens diretas; o bot responde à última mensagem.

```python
from sukarisebot import Bot


class Receptionist(Bot):
    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        if is_new_conversation:
            await self.api.send_message(conversation_id, "Hello! I am the room's bot. Write 'rules'.")
            return
        messages = await self.api.messages(conversation_id)
        if not messages or messages[0].sender_id != user_id:
            return
        if "rules" in messages[0].content.lower():
            await self.api.send_message(conversation_id, "1. Be polite. 2. No spam.")
        else:
            await self.api.send_message(conversation_id, "I did not understand. Write 'rules'.")
```

Lembre-se: o bot não escreve primeiro em uma conversa: quem começa é a pessoa.

## Moderador: silêncio para spam

O bot precisa ser **moderador** da sala (e não só designer).

```python
import time
from collections import defaultdict, deque

from sukarisebot import Bot, ResponseError, User

LIMIT = 5  # messages
WINDOW = 10.0  # seconds


class AntiSpam(Bot):
    def __init__(self) -> None:
        super().__init__()
        self._recent: defaultdict[str, deque[float]] = defaultdict(deque)

    async def on_chat(self, user: User, message: str) -> None:
        if self.is_owner(user):
            return
        now = time.monotonic()
        recent = self._recent[user.id]
        recent.append(now)
        while recent and now - recent[0] > WINDOW:
            recent.popleft()
        if len(recent) > LIMIT:
            recent.clear()
            try:
                await self.api.mute(user.id, 60)
                await self.api.chat(f"{user.username}, please do not spam. A minute of silence.")
            except ResponseError as error:
                await self.api.chat(f"I cannot mute: {error.message}")
```

## Copiar a roupa de um jogador

Com o comando `!copyme` o bot veste a roupa de quem pediu. Trocar a roupa é gratuito enquanto o
dono do bot tiver PREMIUM ativo.

```python
from sukarisebot import Bot, Context, InvalidArgument, ResponseError, command


class Mirror(Bot):
    @command("copyme", cooldown=(1, 30.0), description="put on my outfit")
    async def copyme(self, ctx: Context) -> None:
        outfit = await ctx.api.outfit_of(ctx.user.id)
        try:
            await ctx.api.wear(outfit)
        except InvalidArgument as error:
            await ctx.reply(f"This outfit cannot be worn: {error}")
        except ResponseError as error:
            await ctx.reply(f"It did not work: {error.message}")
        else:
            await ctx.reply("Done!")
```

## Um bot anfitrião: acomoda os convidados

Quando um jogador senta em um móvel, o bot senta no assento vizinho do mesmo móvel (se estiver
livre). Mostra como trabalhar com `Location`.

```python
from sukarisebot import AnchorPosition, Bot, Location, ResponseError, User


class Companion(Bot):
    async def on_user_move(self, user: User, position: Location) -> None:
        if not isinstance(position, AnchorPosition):
            return
        neighbour = AnchorPosition(position.entity_id, position.anchor_ix + 1)
        try:
            await self.api.sit_on(neighbour)
        except ResponseError:
            pass  # there is no neighbouring seat or it is taken
```

## Um aviso em horário programado

```python
from sukarisebot import Bot, every


class Herald(Bot):
    @every(600)
    async def rules(self) -> None:
        await self.api.chat("Reminder: the room has rules. Commands: !help.")
```

## Dois bots na mesma sala se entendem

Um bot avisa o outro pelo canal oculto (os jogadores não veem):

```python
from sukarisebot import Bot, Context, command


class Boss(Bot):
    @command("alarm", owner_only=True, description="raise the alarm for all the bots")
    async def alarm(self, ctx: Context) -> None:
        await self.api.channel("alarm", tags=["security"])
        await ctx.reply("Signal sent.")


class Worker(Bot):
    async def on_channel(self, sender_id: str, message: str, tags: tuple[str, ...]) -> None:
        if message == "alarm" and "security" in tags:
            await self.api.chat("Alarm! Everyone stay calm.")
```

Cada bot é iniciado com o seu próprio token (cada um em seu próprio processo ou em sua própria
tarefa). Os dois precisam estar na mesma sala.

## Uma requisição a um serviço externo

```python
from sukarisebot import Bot, Context, command


class Fact(Bot):
    @command("fact", cooldown=(1, 20.0), description="a random fact")
    async def fact(self, ctx: Context) -> None:
        # The address is made up: put your own service here.
        async with self.http.get("https://example.com/api/fact") as response:
            if response.status != 200:
                await ctx.reply("The fact service is unavailable.")
                return
            await ctx.reply((await response.text())[:300])
```

Não faça chamadas bloqueantes (`requests`, `time.sleep`): elas param o bot inteiro. Use
`self.http` e `await asyncio.sleep(...)`.
