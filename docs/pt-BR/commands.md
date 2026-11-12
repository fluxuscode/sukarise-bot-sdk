[English](../en/commands.md) | [Русский](../ru/commands.md) | **Português (Brasil)**

# Comandos, temporizadores e diálogos

Além dos manipuladores de eventos, o bot tem três mecanismos práticos: **comandos de chat**
(`!roll`), **temporizadores** (fazer algo a cada N segundos) e **diálogos** (fazer uma pergunta e
esperar a resposta). Os três são declarados direto na classe do bot e não exigem registro.

## Comandos: `@command`

```python
import random

from sukarisebot import Bot, Context, command


class Dice(Bot):
    @command("roll", aliases=("dice",), cooldown=(3, 60.0), description="roll a die")
    async def roll(self, ctx: Context) -> None:
        await ctx.reply(f"@{ctx.user.username} rolled {random.randint(1, 6)}")

    @command("shutdown", owner_only=True, description="stop the bot")
    async def shutdown(self, ctx: Context) -> None:
        await ctx.reply("Bye!")
        await self.stop()
```

Um jogador escreve `!roll` no chat público ou em um sussurro, e o método `roll` executa.

### Como o bot entende um comando

- A mensagem deve **começar com o prefixo `!`**. Tudo depois dele é dividido nos espaços; a
  primeira palavra é o nome do comando, e as demais são argumentos.
- O nome não depende de maiúsculas e minúsculas: `!Roll`, `!ROLL` e `!roll` são um só comando.
  Não importa quantos espaços haja entre as palavras, os argumentos são separados um a um.
- Um comando é reconhecido tanto no **chat público** quanto em um **sussurro**.
- O bot não trata a própria mensagem como comando.
- Se não existe esse comando, o bot fica em silêncio, e a mensagem em si ainda vai para `on_chat`.
- Os comandos executam **depois** do manipulador do evento de chat (`on_chat`/`on_whisper`).

### Os parâmetros de `@command`

| Parâmetro | Descrição |
|---|---|
| `name` | o nome do comando: uma palavra sem espaços |
| `aliases` | outros nomes do mesmo comando, por exemplo `("dice", "die")` |
| `description` | uma descrição curta; o `!help` a mostra |
| `cooldown` | `(chamadas, segundos)`: cada jogador pode fazer essa quantidade de chamadas em qualquer janela desse tamanho; acima do limite o bot pede que esperem |
| `owner_only` | `True`: só o dono da sala executa o comando; aos demais o bot responde com uma recusa |

Parâmetros errados (um nome vazio, `cooldown=(0, 10)` e assim por diante) lançam
`InvalidArgument` **quando a classe é definida**, e não no meio do funcionamento do bot.

Nomes e apelidos devem ser únicos: um nome repetido lança `InvalidArgument` ("o comando …
já está registrado") quando o bot é criado.

### `Context`: o que um comando recebe

O único argumento de um método de comando é um `Context`:

| Membro | O que é |
|---|---|
| `ctx.user` | quem chamou (`User`) |
| `ctx.name` | o nome canônico do comando (mesmo que tenha sido chamado por um apelido), em minúsculas |
| `ctx.args` | uma tupla com as palavras depois do nome |
| `ctx.arg(i)` | o `i`-ésimo argumento ou `None` se não houver |
| `ctx.rest()` | todos os argumentos em uma única string |
| `ctx.whisper` | `True` se o comando veio em um sussurro |
| `ctx.text` | a mensagem original inteira |
| `ctx.api` | as ações do bot (o mesmo que `self.api`) |
| `await ctx.reply(text)` | responder **para onde o comando veio**: sussurro a um sussurro, chat público a uma fala no chat |

Para a mensagem `!say hello all`: `ctx.args == ("hello", "all")`, `ctx.arg(0) == "hello"`,
`ctx.rest() == "hello all"`.

```python
from sukarisebot import Bot, Context, command


class Echo(Bot):
    @command("say", description="repeat the text")
    async def say(self, ctx: Context) -> None:
        text = ctx.rest()
        await ctx.reply(text if text else "Say what? Write: !say text")
```

### Limite de frequência (`cooldown`)

`cooldown=(3, 60.0)` significa "no máximo três chamadas a cada 60 segundos por jogador". É uma
janela deslizante: um jogador que excede o limite recebe a resposta "aguarde N s…", e o contador
se libera à medida que as chamadas antigas saem da janela. O limite funciona separadamente para
cada jogador e cada comando. Uma chamada rejeitada por causa de `owner_only` não gasta o limite.
O bot esquece sozinho os registros de jogadores que não escrevem há muito tempo, então a memória
não cresce a cada jogador novo.

### Só para o dono: `owner_only`

"Dono" aqui é o **dono da sala** em que o bot trabalha (`bot.owner_id`), e não o dono do bot.
Em geral é a mesma pessoa, mas não necessariamente. Dá para verificar a mesma coisa no seu
próprio código com `self.is_owner(user)`.

### O comando `!help`

O bot cria o `!help` sozinho e lista todos os comandos com as descrições. Os comandos são
listados na ordem alfabética dos **nomes dos métodos**, e o `!help` vem por último. Para
substituí-lo pelo seu, declare um comando `help`:

```python
from sukarisebot import Bot, Context, command


class Polite(Bot):
    @command("help")
    async def help(self, ctx: Context) -> None:
        await ctx.reply("Write !roll to roll a die.")
```

### O que o bot diz sozinho: `Phrases`

O bot diz três frases em nome próprio: a recusa a quem não é dono, o pedido para esperar e a
resposta ao `!help`. Por padrão elas estão em russo. Você pode substituí-las definindo na classe
do bot o atributo `phrases`:

```python
from sukarisebot import Bot, Phrases


class English(Bot):
    phrases = Phrases(
        owner_only="@{username}, {prefix}{command} is for the room owner.",
        cooldown="@{username}, wait {seconds} s before {prefix}{command} again.",
        help="Commands: {commands}",
    )
```

| Campo de `Phrases` | Quando é usado | Campos do modelo |
|---|---|---|
| `owner_only` | alguém que não é dono chamou um comando `owner_only` | `{username}`, `{prefix}`, `{command}` |
| `cooldown` | o comando foi chamado com frequência demais | `{username}`, `{prefix}`, `{command}`, `{seconds}` |
| `help` | a resposta ao `!help` | `{commands}`: a lista de comandos |
| `help_separator` | o separador dos comandos na lista | — |

O modelo é formatado com `str.format`: use apenas os campos listados. Um campo desconhecido
lança `KeyError`, que vai para `on_error`.

## Temporizadores: `@every`

```python
from sukarisebot import Bot, every


class Herald(Bot):
    @every(300)
    async def announce(self) -> None:
        await self.api.chat("Do not forget the room rules.")
```

`@every(seconds)` executa o método a cada `seconds` segundos enquanto o bot estiver conectado.

- O método não recebe argumentos (além de `self`).
- A **primeira execução** é `seconds` segundos depois de conectar, e não na hora.
- A próxima execução é contada a partir do *fim* da anterior, então o período real é `seconds`
  mais o tempo que o método leva. As execuções de um mesmo temporizador não se sobrepõem.
- Um erro em um temporizador não o interrompe: vai para [`on_error`](handlers.md#on_error)
  (com `event=None`).
- Enquanto não há conexão, as execuções são puladas. Na reconexão os temporizadores não são
  reiniciados; eles continuam.
- Um temporizador trabalha em uma tarefa separada, então pode executar enquanto um manipulador
  de evento espera em um `await`.
- `seconds` deve ser um número finito positivo, senão `InvalidArgument`.

## Diálogos: `wait_for`

`await self.wait_for(kind, check, timeout=...)` espera o **próximo** evento do tipo `kind` que
passe na verificação `check`. Ideal para "fiz uma pergunta, espero a resposta":

```python
from sukarisebot import Bot, ChatEvent, Context, command


class Riddle(Bot):
    @command("riddle", cooldown=(1, 60.0), description="a riddle")
    async def riddle(self, ctx: Context) -> None:
        await ctx.reply("What has keys but cannot open locks? Answer by whisper.")
        try:
            answer = await self.wait_for(
                ChatEvent,
                lambda event: event.whisper and event.user.id == ctx.user.id,
                timeout=60,
            )
        except TimeoutError:
            await ctx.reply("Time is up.")
            return
        if answer.message.strip().lower() == "piano":
            await ctx.reply("Correct!")
        else:
            await ctx.reply("Wrong.")
```

| Parâmetro | Descrição |
|---|---|
| `kind` | a classe do evento: `ChatEvent`, `UserJoinedEvent` e assim por diante |
| `check` | uma função "o evento serve?"; `None`: qualquer evento serve |
| `timeout` | quantos segundos esperar; quando acabam, `TimeoutError` |

O que você precisa saber:

1. **Sempre defina um `timeout`.** Sem ele a espera pode nunca terminar.
2. **Enquanto um comando espera, o bot não trata outros eventos.** Os manipuladores vão um de
   cada vez (veja [Como o SDK funciona](architecture.md#como-um-evento-chega-a-um-manipulador));
   um comando à espera ocupa a fila. Para um diálogo com um jogador em uma sala tranquila isso é
   normal; para vários jogadores ao mesmo tempo, inicie o diálogo como uma tarefa separada
   (abaixo).
3. **O `wait_for` só vê eventos que chegaram depois da chamada.** Uma resposta que já chegou e
   está na fila antes de o comando alcançar o `wait_for` é perdida: isso acontece quando o
   jogador escreve a resposta na hora e o bot está atrasado. Faça a pergunta primeiro e depois
   espere.
4. **A espera dispara no momento em que o evento chega**, antes da fila, então o comando à
   espera verá o evento de que precisa mesmo ocupando a fila. Depois disso o evento segue o
   caminho normal para os manipuladores `on_...` (inclusive `on_whisper`) e para os comandos.
5. **O evento precisa chegar ao bot.** O chat e as entradas e saídas sempre chegam. Para esperar
   qualquer outro evento, sobrescreva o manipulador dele (um vazio basta), senão não há
   assinatura.
6. Se a função `check` lançar uma exceção, ela sai do `wait_for` no seu código.

### Diálogos com vários jogadores ao mesmo tempo

Inicie o diálogo como uma tarefa separada, para que o comando termine na hora e a fila de eventos
não fique bloqueada. Não esqueça de guardar uma referência à tarefa e de passar os erros dela ao
`on_error`:

```python
import asyncio
from collections.abc import Awaitable

from sukarisebot import Bot, ChatEvent, Context, command


class Quiz(Bot):
    def __init__(self) -> None:
        super().__init__()
        self._dialogs: set[asyncio.Task[None]] = set()

    def spawn(self, work: Awaitable[None]) -> None:
        """Start a dialogue in the background: keep the reference, send errors to on_error."""
        task = asyncio.create_task(self._guarded(work))
        self._dialogs.add(task)
        task.add_done_callback(self._dialogs.discard)

    async def _guarded(self, work: Awaitable[None]) -> None:
        try:
            await work
        except Exception as error:
            await self.on_error(error, None)

    @command("quiz", cooldown=(1, 30.0), description="a quiz")
    async def quiz(self, ctx: Context) -> None:
        self.spawn(self._ask(ctx))  # the command finishes at once

    async def _ask(self, ctx: Context) -> None:
        await ctx.api.whisper(ctx.user.id, "What is 6 x 7?")
        try:
            answer = await self.wait_for(
                ChatEvent,
                lambda event: event.whisper and event.user.id == ctx.user.id,
                timeout=60,
            )
        except TimeoutError:
            await ctx.api.whisper(ctx.user.id, "Time is up.")
            return
        verdict = "Correct!" if answer.message.strip() == "42" else "Wrong."
        await ctx.api.whisper(ctx.user.id, verdict)
```

## Dados em memória: `state` e `user_state`

- `self.state` é um dicionário livre `dict[str, object]` para os dados do bot.
- `self.user_state(user_id)` é um dicionário pessoal por jogador; é criado no primeiro uso.

Ambos vivem enquanto o processo roda e **não são salvos em disco**. Para dados que precisam
sobreviver a uma reinicialização use o [`JsonStore`](tools.md#jsonstore-dados-entre-execuções).

```python
from sukarisebot import Bot, Context, command


class Counter(Bot):
    @command("count", description="count my calls")
    async def count(self, ctx: Context) -> None:
        state = self.user_state(ctx.user.id)
        calls = state.get("calls", 0)
        calls = (calls if isinstance(calls, int) else 0) + 1
        state["calls"] = calls
        await ctx.reply(f"@{ctx.user.username}, you have called me {calls} time(s).")
```

## Como testar comandos

Comandos e diálogos são testados sem servidor com o `Harness`; execute um diálogo com `wait_for`
como uma tarefa separada: veja [Testes](testing.md).
