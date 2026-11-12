[English](../en/tools.md) | [Русский](../ru/tools.md) | **Português (Brasil)**

# Ferramentas

As partes auxiliares do SDK: a lista da sala, o modo "sala limpa", o armazenamento de dados, o
cliente HTTP, a verificação da roupa e o início pela linha de comando.

## A lista da sala (`bot.room`)

O `bot.room` (a classe `Room`) responde à pergunta "quem está na sala agora e onde". O objeto é
**somente leitura**: o próprio SDK o preenche.

| Membro | O que faz |
|---|---|
| `room.users()` | uma lista de `RoomUser`: todos que estão na sala agora |
| `room.get(user_id)` | o registro de uma pessoa pelo identificador, ou `None` |
| `room.find("@Alice")` | um registro pelo nome; maiúsculas e um `@` inicial não importam; `None` se não houver |
| `user_id in room` | se uma pessoa está na sala |
| `len(room)` | quantas pessoas estão na sala |
| `room.seeded` | `True` se a lista tem todos que estão na sala, e não só os vistos entrando |

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

### O que atualiza a lista

Ao conectar, o SDK carrega a lista do servidor (`await bot.refresh_room()` é chamado sozinho).
Depois disso os **eventos** a atualizam. O SDK sempre recebe as entradas e saídas das pessoas
(exceto no modo "sala limpa"), então a lista de pessoas continua correta sem manipulador algum.
Já os movimentos só chegam ao bot se um manipulador for sobrescrito para eles (veja
[Assinaturas de eventos](architecture.md#assinaturas-de-eventos)): para o `bot.room` saber onde
cada um está de pé ou sentado, sobrescreva `on_user_move`. O corpo do manipulador pode ficar
vazio:

```python
from sukarisebot import Bot, Location, User


class Tracker(Bot):
    """Keeps the positions in bot.room current and does nothing else."""

    async def on_user_move(self, user: User, position: Location) -> None:
        pass
```

Sem `on_user_move`, a posição de uma pessoa na lista é onde ela estava ao entrar ou na última
carga. Você pode atualizar a lista por completo a qualquer momento: `await self.refresh_room()`
(uma requisição `info`). Antes da versão 0.3.0 as entradas e saídas também só atualizavam a lista
se `on_user_join` e `on_user_leave` fossem sobrescritos.

## Modo "sala limpa"

`start(clean_room=True)` (ou `run(clean_room=True)`): o bot **não faz nenhuma requisição que o
código dele não pediu**. Em particular, ele não pede a lista de pessoas ao conectar, então o
`bot.room` começa vazio (`seeded == False`) e se preenche com os eventos de entrada. A lista
completa é carregada explicitamente: `await self.refresh_room()`. Nesse modo o SDK também não se
inscreve nas entradas e saídas das pessoas, até que você mesmo sobrescreva os manipuladores delas.

O modo é para bots que só escutam: eles não geram tráfego extra. Para um exemplo veja
[`examples/clean_room.py`](../../examples/clean_room.py). Pela linha de comando:
`python -m sukarisebot module:Class --clean-room`.

## `JsonStore`: dados entre execuções

`self.state` e `self.user_state()` vivem apenas enquanto o processo roda. Para dados que precisam
sobreviver a uma reinicialização existe o `JsonStore`: um pequeno armazenamento "chave → valor
JSON" em um único arquivo.

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

| Método | O que faz |
|---|---|
| `await store.get(key, default=None)` | o valor pela chave, ou `default` |
| `await store.set(key, value)` | gravar um valor |
| `await store.update(key, change, default=None)` | substituir o valor pelo resultado de `change(antigo)` e devolver o novo |
| `await store.all()` | uma cópia de todos os registros (por exemplo, para um ranking) |
| `store.path` | o caminho do arquivo |

O que você precisa saber:

- **A chave é o identificador de um jogador (`user.id`), e não o nome**: o nome pode ser trocado.
- O valor é um valor JSON: `None`, `bool`, um número, uma string, uma lista ou um dicionário. O
  tipo `JsonValue` descreve isso para o verificador de tipos.
- **A gravação é atômica**: os dados são escritos em um arquivo temporário que depois substitui o
  antigo, então uma falha no meio da gravação não deixa um arquivo pela metade. As operações de
  disco rodam em uma thread de trabalho e não param o bot.
- **Alterações simultâneas não se perdem**: `set` e `update` entram em fila. Para "ler, alterar,
  gravar" use `update`, e não um par `get` + `set`.
- Se uma gravação falhar (por exemplo, o valor não pode ser gravado como JSON), o armazenamento
  continua como estava.
- O arquivo é lido inteiro no primeiro uso e mantido na memória; cada alteração o grava inteiro.
  Serve para dados pequenos, não para bancos de dados grandes.
- Se o arquivo existir mas não tiver um objeto JSON, o primeiro uso lança `ValueError`.

## O cliente HTTP `bot.http`

Para requisições a outros serviços (cotações, um tradutor, o seu banco de dados) o bot tem um
cliente `aiohttp` compartilhado, o `bot.http`. Ele é criado no primeiro uso, fecha sozinho quando
o bot para, e cada requisição tem um tempo limite de 10 segundos.

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

Use-o em vez de criar um cliente em cada manipulador.

## A roupa: `outfit_problems` e `category_of`

`api.wear(items)` primeiro verifica a roupa do lado do SDK, para que você receba um
`InvalidArgument` claro em vez de uma recusa do servidor. Você pode chamar a mesma verificação
você mesmo:

```python
from sukarisebot import Item, outfit_problems

items = [Item(type="clothing", amount=1, id="shirt-n_plaid_blackwhite")]
for problem in outfit_problems(items):
    print(problem)
```

`outfit_problems(items)` retorna uma lista de problemas (vazia: a roupa está correta). Ele
verifica que:

- todos os itens são roupas (`type == "clothing"`);
- nenhum item se repete;
- cada **categoria básica** (`shirt`, `pants`, `skirt`, `dress`, `fullsuit` e as partes do corpo)
  aparece no máximo uma vez;
- todas as partes do corpo estão presentes: `body-flesh`, `eye`, `eyebrow`, `nose`, `mouth`;
- o corpo está coberto: uma camisa e calça, uma camisa e saia, um vestido ou um macacão.

`category_of(item_id)` determina a categoria básica pelo identificador de um item (ele começa com
o nome da categoria) ou retorna `None` para acessórios.

O SDK lê a categoria do identificador, enquanto o servidor a lê do tipo do item no catálogo.
Por isso os itens com identificadores `bag-…`, sob os quais pode haver qualquer coisa (uma
sobrancelha, uma camisa, uma calça), não são classificados pelo SDK, e ele não conta como erro o
que eles são capazes de suprir: os dois últimos pontos da lista acima só são verificados se não
houver desses itens em número suficiente para cobrir o que falta. Antes, roupas assim, por
exemplo copiadas de uma pessoa com `outfit_of`, eram recusadas por engano.

O SDK não verifica a posse dos itens: só o servidor a conhece. Enquanto o dono do bot tiver
PREMIUM ativo, trocar a roupa é gratuito: o bot pode vestir qualquer item do catálogo. O bot pode
descobrir a própria roupa atual com `await bot.my_outfit()`.

## Início pela linha de comando

Você pode iniciar um bot sem um script de inicialização próprio, como o comando oficial
`highrise`:

```bash
python -m sukarisebot examples.dice:Dice --room room-... --token srbot_...
sukarisebot examples.dice:Dice --clean-room
```

| Parâmetro | Descrição |
|---|---|
| `module:Class` | o bot no formato "nome do módulo, dois-pontos, nome da classe"; o módulo é procurado no diretório atual e por um `import` comum |
| `--room ID` | o identificador da sala (ou a variável `SUKARISEBOT_ROOM_ID`) |
| `--token TOKEN` | o token do bot (ou a variável `SUKARISEBOT_TOKEN`) |
| `--url URL` | o endereço do gateway (ou a variável `SUKARISEBOT_URL`) |
| `--clean-room` | o modo "sala limpa" |
| `--log-level LEVEL` | `DEBUG`, `INFO` (o padrão), `WARNING` ou `ERROR`; qualquer outro valor é um erro de uso |

Código de saída: `0`: normal, `1`: o servidor recusou (`ConnectionRefused` e outros), `2`: o bot
não foi encontrado (o módulo não pode ser importado ou a classe não herda `Bot`). O bot é criado
por um construtor **sem argumentos**.

A mesma busca está disponível pelo código: `load_bot("module:Class")` retorna um bot pronto.

## Partes de baixo nível

Para tarefas fora do comum o pacote também exporta suas classes internas:

- `Engine`: a conexão: websocket, fila de eventos, reconexão. É criado pelo próprio `Bot`; você
  precisa dele se quiser gerenciar a conexão à mão.
- `Requester`: a interface "enviar uma requisição, receber uma resposta". O `Engine` e o
  `RecordingRequester` de testes a implementam. A `BotAPI` depende só dela.
- `Commands`, `Command`, `CommandSpec`, `CommandHandler`: o registro de comandos e suas partes.

Um bot comum não precisa delas. Como funcionam está em [Como o SDK funciona](architecture.md) e
[Protocolo](protocol.md).
