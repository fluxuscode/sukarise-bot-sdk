[English](../en/api.md) | [Русский](../ru/api.md) | **Português (Brasil)**

# Referência da `BotAPI`

Tudo o que um bot sabe fazer são métodos do objeto `BotAPI`. Em um bot em execução ele está
disponível como `self.api` e, em um comando, também como `ctx.api`. Cada método é **uma ação
assíncrona**: chame-o com `await`.

```python
await self.api.chat("Hello!")
users = await self.api.list_room_users()
```

## Regras gerais

**Verificado antes do envio.** Os argumentos são verificados antecipadamente. Texto vazio, uma
reação desconhecida, uma coordenada fora do intervalo permitido, um número de assento fora de
0…255 ou um identificador maior que o limite do servidor (emote: 96 bytes, móvel e conversa: 128,
item: 256) lançam `InvalidArgument` na sua linha de código, e a requisição não é enviada.

**Exceções.** Qualquer método pode lançar:

| Exceção | Quando |
|---|---|
| `InvalidArgument` | um argumento está errado; a requisição não foi enviada |
| `ResponseError` | o servidor recusou (sem direitos, a pessoa não está na sala, e assim por diante); o texto da recusa está em `error.message`, em inglês |
| `RateLimited` | o servidor recusou por causa do limite de frequência e as novas tentativas do SDK não resolveram (uma subclasse de `ResponseError`) |
| `NotConnected` | o bot não tem conexão |
| `RequestTimeout` | o servidor não respondeu em 10 segundos |

As tabelas abaixo listam apenas as causas específicas de cada método. Para detalhes veja
[Erros e recusas](errors.md).

**Limites de frequência.** Todo método tem uma categoria de limite (a coluna "Limite"). Se o
orçamento acabar, o SDK espera sozinho; um bot normalmente não vê uma recusa por limite. Veja
[Como o SDK funciona](architecture.md#limites-de-frequência).

**2D e 3D.** Um bot funciona em salas comuns (2D) e em salas 3D. A coluna "Salas" mostra onde um
método está disponível; em um mundo 3D o bot recebe o mesmo que em 2D, exceto as reações das
pessoas, que o cliente não envia lá (veja
[O que funciona e o que não funciona](../../README.pt-BR.md#o-que-funciona-e-o-que-não-funciona)).

## Resumo

| Método | O que faz | Limite | Salas |
|---|---|---|---|
| [`chat(message)`](#chat) | falar no chat público | `chat` | 2D, 3D |
| [`whisper(user_id, message)`](#whisper) | sussurrar a uma pessoa | `chat` | 2D, 3D |
| [`channel(message, tags, only_to)`](#channel) | uma mensagem oculta a outros bots | `channel` | 2D, 3D |
| [`emote(emote_id, target_user_id)`](#emote) | executar um emote | `emote` | 2D, 3D |
| [`react(reaction, target_user_id)`](#react) | enviar uma reação | `emote` | 2D, 3D |
| [`move_to(position)`](#move_to) | andar até um ponto | `move` | 2D, 3D |
| [`sit_on(anchor)`](#sit_on) | sentar em um assento de móvel | `move` | 2D, 3D |
| [`teleport_user(user_id, position)`](#teleport_user) | mover uma pessoa | `teleport` | 2D, 3D |
| [`list_room_users()`](#list_room_users) | quem está na sala e onde | `info` | 2D, 3D |
| [`privileges(user_id)`](#privileges) | os direitos de uma pessoa na sala | `info` | 2D, 3D |
| [`set_privileges(user_id, moderator, designer)`](#set_privileges) | conceder/retirar direitos | `moderate` | sempre recusado no SukaRise |
| [`moderate(user_id, action, seconds)`](#moderate) | kick/ban/unban/mute | `moderate` | 2D, 3D |
| [`kick(user_id)`](#kick) | expulsar | `moderate` | 2D, 3D |
| [`ban(user_id, seconds)`](#ban) | banir | `moderate` | 2D, 3D |
| [`unban(user_id)`](#unban) | retirar um banimento | `moderate` | 2D, 3D |
| [`mute(user_id, seconds)`](#mute) | silenciar | `moderate` | 2D, 3D |
| [`tip(user_id, gold_bar)`](#tip) | uma gorjeta com o ouro do bot | `tip` | 2D, 3D |
| [`buy_item(item_id)`](#buy_item) | comprar um item com o ouro do bot | `shop` | 2D, 3D |
| [`conversations(not_joined, last_id)`](#conversations) | as conversas diretas do bot | `info` | 2D, 3D |
| [`messages(conversation_id, last_message_id)`](#messages) | as mensagens de uma conversa | `info` | 2D, 3D |
| [`send_message(conversation_id, content)`](#send_message) | responder em uma conversa | `message` | 2D, 3D |
| [`send_bulk_message(user_ids, content)`](#send_bulk_message) | escrever para várias pessoas | `message` | 2D, 3D |
| [`leave_conversation(conversation_id)`](#leave_conversation) | sair de uma conversa | `message` | 2D, 3D |
| [`wallet()`](#wallet) | todas as moedas do bot | `info` | 2D, 3D |
| [`gold()`](#gold) | o ouro do bot | `info` | 2D, 3D |
| [`outfit_of(user_id)`](#outfit_of) | a roupa de uma pessoa | `info` | 2D, 3D |
| [`inventory()`](#inventory) | o guarda-roupa do bot | `info` | 2D, 3D |
| [`wear(items)`](#wear) | trocar a roupa do bot | `info` | 2D, 3D |
| [`split_message(text, limit)`](#split_message) | dividir um texto longo | — | uma função auxiliar |

## Chat

### `chat`

```python
async def chat(self, message: str) -> None
```

Dizer uma fala no chat público da sala. Um texto com mais de **500 caracteres** é dividido nos
espaços e sai como várias mensagens seguidas.

| Parâmetro | Descrição |
|---|---|
| `message` | o texto da fala |

`InvalidArgument`: o texto está vazio ou só tem espaços. `ResponseError`: por exemplo, o bot foi
silenciado.

```python
await self.api.chat("Hello, everyone!")
```

### `whisper`

```python
async def whisper(self, user_id: str, message: str) -> None
```

Uma mensagem privada a uma pessoa **na sala**. Só o destinatário e o bot a veem. Um texto longo
é dividido em vários sussurros.

| Parâmetro | Descrição |
|---|---|
| `user_id` | o destinatário; precisa estar na sala |
| `message` | o texto |

`ResponseError`: o destinatário não está na sala. Para mensagens a pessoas que não estão na sala
use as conversas diretas ([`send_message`](#send_message)).

### `channel`

```python
async def channel(
    self,
    message: str,
    *,
    tags: Iterable[str] = (),
    only_to: Iterable[str] | None = None,
) -> None
```

Uma mensagem oculta a outros **bots** nesta sala. Os jogadores não a veem. Os destinatários a
ouvem em [`on_channel`](handlers.md#on_channel); quem envia não recebe a própria mensagem. Assim
os bots de uma mesma sala podem se entender.

| Parâmetro | Descrição |
|---|---|
| `message` | o texto, no máximo **1024 bytes** em UTF-8 |
| `tags` | etiquetas, até 10, cada uma com no máximo **32 bytes** em UTF-8 (uma letra cirílica ocupa dois bytes); os destinatários as usam para escolher mensagens |
| `only_to` | identificadores dos bots destinatários (até 50); `None`: todos os bots da sala |

## Linguagem corporal

### `emote`

```python
async def emote(self, emote_id: str, *, target_user_id: str | None = None) -> None
```

Executar um emote: sozinho ou na direção de uma pessoa. **Um bot executa emotes pagos de graça se
o dono dele tiver PREMIUM ativo.** Emotes em par (com um parceiro) não estão disponíveis a um
bot.

| Parâmetro | Descrição |
|---|---|
| `emote_id` | o identificador do emote, por exemplo `"emote-wave"`, no máximo 96 bytes |
| `target_user_id` | a quem dirigir; `None`: a ninguém. O destinatário precisa estar na sala (em 3D também); como em 2D, o evento do emote não o informa |

`ResponseError`: não existe esse emote, ele é em par, é pago e o dono não tem PREMIUM, ou o
destinatário não está na sala.

### `react`

```python
async def react(self, reaction: Reaction, target_user_id: str) -> None
```

Enviar uma reação a uma pessoa: `"clap"` (aplausos), `"heart"` (um coração), `"thumbs"` (um
joinha), `"wave"` (um cumprimento), `"wink"` (uma piscadela).

`InvalidArgument`: uma reação desconhecida. `ResponseError`: o destinatário não está na sala.

```python
await self.api.react("heart", user.id)
```

## Movimento

### `move_to`

```python
async def move_to(self, position: Position) -> None
```

Mandar o bot andando até um ponto no chão. As coordenadas são números finitos dentro de
**±1000**; a direção `facing` é `FrontRight`, `FrontLeft`, `BackRight` ou `BackLeft`.

```python
from sukarisebot import Position

await self.api.move_to(Position(5.5, 0.0, 5.5, facing="FrontLeft"))
```

**Em um mundo 3D uma caminhada não tem resposta.** A requisição sai e conta como feita mesmo que
o mundo não consiga traçar um caminho (um ponto atrás de um móvel ou fora do chão): o bot então
simplesmente fica onde está e nenhum `ResponseError` chega. Se importa saber se o bot chegou, leia
a posição dele (`list_room_users`) um ou dois segundos depois e, se falhou, tente outro ponto
próximo.

### `sit_on`

```python
async def sit_on(self, anchor: AnchorPosition) -> None
```

Sentar o bot em um assento de um móvel. Pegue o identificador do móvel e o número do assento
(`entity_id`, `anchor_ix`) da posição de uma pessoa que está sentada nesse móvel: para quem está
sentado, `location` é uma `AnchorPosition`. O identificador do móvel tem no máximo 128 bytes, e o
número do assento é um inteiro de 0 a 255.

```python
from sukarisebot import AnchorPosition, Bot, Location, User


class Follower(Bot):
    async def on_user_move(self, user: User, position: Location) -> None:
        if isinstance(position, AnchorPosition):
            await self.api.sit_on(position)
```

`ResponseError`: não existe esse assento ou ele está ocupado. Em um mundo 3D o bot primeiro anda
até o assento: se o mundo não o sentou em 8 segundos, isso é a recusa "The bot could not reach
that seat", e o bot fica onde estava.

### `teleport_user`

```python
async def teleport_user(self, user_id: str, position: Position) -> None
```

Mover uma pessoa instantaneamente para um ponto no chão. **São necessários direitos de
moderador** na sala: só os de designer não bastam. O bot segue as mesmas regras que um moderador
humano.

## A sala e os direitos

### `list_room_users`

```python
async def list_room_users(self) -> list[RoomUser]
```

Quem está na sala agora e onde está de pé ou sentado. Em geral não é preciso chamá-lo à mão: a
lista é mantida pelo [`bot.room`](tools.md#a-lista-da-sala-botroom). Retorna uma lista de
`RoomUser` (`.user`, `.location`).

### `privileges`

```python
async def privileges(self, user_id: str) -> RoomPermissions
```

Os direitos de uma pessoa nesta sala: `.moderator`, `.designer`. `None` em um campo significa que
o servidor não informou.

```python
permissions = await self.api.privileges(user.id)
if permissions.moderator:
    ...
```

### `set_privileges`

```python
async def set_privileges(
    self,
    user_id: str,
    *,
    moderator: bool | None = None,
    designer: bool | None = None,
) -> None
```

Conceder ou retirar direitos de moderador e de designer (`None`: não alterar).

> **No servidor do SukaRise os bots não podem mudar direitos**: só o dono da sala e a equipe
> podem. A chamada sempre termina em um `ResponseError`. O método foi mantido por compatibilidade
> com o código escrito para o SDK oficial do Highrise.

## Moderação

Para moderar, o bot precisa ter **direitos de moderador** na sala: o direito de "designer", que
basta para entrar, não serve. O bot segue as mesmas regras que uma pessoa: o dono da sala não
pode ser punido, e um moderador só pode ser punido pelo dono. As ações estão disponíveis tanto
em salas 2D quanto em 3D.

### `moderate`

```python
async def moderate(self, user_id: str, action: ModerationAction, *, seconds: int | None = None) -> None
```

Expulsar, banir, desbanir ou silenciar.

| Parâmetro | Descrição |
|---|---|
| `user_id` | a quem aplicar |
| `action` | `"kick"`, `"ban"`, `"unban"` ou `"mute"` |
| `seconds` | o prazo de um banimento ou silenciamento, de 0 a 2.592.000 (30 dias); `None`: sem prazo definido, o servidor decide |

`InvalidArgument`: uma ação desconhecida ou um prazo fora do intervalo. `ResponseError`: sem
direitos de moderador ou o alvo é protegido. As formas curtas vêm a seguir.

### `kick`

```python
async def kick(self, user_id: str) -> None
```

Expulsar da sala. O mesmo que `moderate(user_id, "kick")`.

### `ban`

```python
async def ban(self, user_id: str, *, seconds: int | None = None) -> None
```

Banir. O mesmo que `moderate(user_id, "ban", seconds=seconds)`.

### `unban`

```python
async def unban(self, user_id: str) -> None
```

Retirar um banimento ou silenciamento. O mesmo que `moderate(user_id, "unban")`.

### `mute`

```python
async def mute(self, user_id: str, seconds: int) -> None
```

Silenciar por um prazo: a pessoa não consegue escrever no chat. O mesmo que
`moderate(user_id, "mute", seconds=seconds)`.

```python
from sukarisebot import Bot, ResponseError, User


class Guard(Bot):
    async def on_chat(self, user: User, message: str) -> None:
        if "spam" in message.lower():
            try:
                await self.api.mute(user.id, 60)
            except ResponseError:
                await self.api.chat("I cannot mute: I have no moderator rights.")
```

## Gorjetas e compras

### `tip`

```python
async def tip(self, user_id: str, gold_bar: GoldBar) -> bool
```

Dar a uma pessoa na sala uma gorjeta em uma barra de ouro **da carteira do bot**. Retorna `True`
se a gorjeta foi enviada e `False` se o bot não tem ouro suficiente (isso é uma resposta, não um
erro; nada é cobrado). Quem envia paga um pouco mais do que o destinatário recebe: por exemplo,
11 de ouro por `gold_bar_10`.

As barras permitidas (`GoldBar`): `gold_bar_1`, `gold_bar_5`, `gold_bar_10`, `gold_bar_50`,
`gold_bar_100`, `gold_bar_500`, `gold_bar_1k`, `gold_bar_5000`, `gold_bar_10k`; o número é
quanto ouro o destinatário recebe. O destinatário precisa estar na sala.

```python
paid = await self.api.tip(user.id, "gold_bar_10")
if not paid:
    await self.api.chat("Not enough gold :(")
```

### `buy_item`

```python
async def buy_item(self, item_id: str) -> bool
```

Comprar um item na loja **com o ouro do bot**. Os bots só podem comprar itens que a loja vende
por ouro. Retorna `True` se comprou e `False` se faltou ouro. O que foi comprado aparece em
[`inventory`](#inventory). O identificador tem no máximo 256 bytes; os espaços nas pontas são
descartados.

## Mensagens diretas

Mensagens diretas são conversas fora da sala. Uma pessoa escreve ao bot pela interface comum do
jogo; o pedido de conversa é aceito pelo bot na hora. O bot **responde** nas conversas em que já
está e não as inicia. O bot participa apenas de conversas diretas (não de grupos) e envia apenas
texto. O fluxo: [`on_message`](handlers.md#on_message) avisa de uma mensagem nova →
[`messages`](#messages) lê → [`send_message`](#send_message) responde.

### `conversations`

```python
async def conversations(self, *, not_joined: bool = False, last_id: str | None = None) -> ConversationPage
```

As conversas diretas do bot, 20 por vez. Para a próxima página passe em `last_id` o
identificador da última conversa da página atual. `not_joined=True` mostra os pedidos ainda não
aceitos; como os pedidos são aceitos pelo bot na hora, em geral não há nenhum.

### `messages`

```python
async def messages(self, conversation_id: str, *, last_message_id: str | None = None) -> list[DirectMessage]
```

As mensagens de uma conversa, **as mais novas primeiro**, 20 por vez. Ler a página mais nova
marca a conversa como lida. Para voltar no tempo, passe em `last_message_id` o identificador da
mensagem mais antiga que você tem.

### `send_message`

```python
async def send_message(self, conversation_id: str, content: str) -> None
```

Responder em uma conversa. Um texto com mais de **1000 caracteres** é dividido em várias
mensagens.

### `send_bulk_message`

```python
async def send_bulk_message(self, user_ids: Sequence[str], content: str) -> None
```

Escrever para **até 100** pessoas de uma vez, mas só para aquelas com quem o bot já tem uma
conversa (que escreveram a ele). A mensagem não vai para as demais; se não chegou a ninguém, é
uma recusa. O texto tem no máximo 1000 caracteres (aqui ele não é dividido).

### `leave_conversation`

```python
async def leave_conversation(self, conversation_id: str) -> None
```

Sair de uma conversa.

## Carteira, guarda-roupa e inventário

### `wallet`

```python
async def wallet(self) -> list[CurrencyItem]
```

Todas as moedas do bot. O ouro é o elemento com `type == "gold"`.

### `gold`

```python
async def gold(self) -> int
```

O ouro do bot (0 se não houver). Um invólucro prático sobre `wallet()`. O bot recebe ouro como
gorjeta; o dono o retira no painel pessoal, no cartão do bot.

### `outfit_of`

```python
async def outfit_of(self, user_id: str) -> list[Item]
```

O que uma pessoa (ou o próprio bot) está vestindo agora. O bot também pode descobrir a própria
roupa com `await self.my_outfit()`.

### `inventory`

```python
async def inventory(self) -> list[Item]
```

As roupas que o bot possui.

### `wear`

```python
async def wear(self, items: Sequence[Item]) -> None
```

Substituir a roupa do bot por inteiro, de 1 a 64 itens. Antes de enviar, o SDK verifica a roupa
([`outfit_problems`](tools.md#a-roupa-outfit_problems-e-category_of)): todos os itens são roupas,
sem repetições, cada categoria básica aparece uma vez, as partes do corpo estão presentes e o
corpo está coberto. O SDK não classifica itens com identificadores `bag-…` (o servidor determina
o tipo deles pelo catálogo, e pode ser qualquer coisa, por exemplo uma sobrancelha), então eles
podem suprir o que falta. Depois o servidor verifica a roupa. Enquanto o dono do bot tiver PREMIUM
ativo, trocar a roupa é **gratuito**: o bot pode vestir qualquer item do catálogo sem precisar
comprá-lo. O dono pode escrever `myoutfit` ao bot no chat ou em um sussurro, e o bot veste *a
roupa atual do dono*.

`InvalidArgument`: a roupa viola as regras (os motivos estão listados no texto). `ResponseError`:
o dono não tem PREMIUM, ou a roupa tem um item que não está no catálogo.

```python
from sukarisebot import Bot, Context, command


class Mirror(Bot):
    @command("copyme", description="put on my outfit")
    async def copyme(self, ctx: Context) -> None:
        outfit = await ctx.api.outfit_of(ctx.user.id)
        await ctx.api.wear(outfit)
        await ctx.reply("Done!")
```

## Uma função auxiliar

### `split_message`

```python
def split_message(text: str, limit: int = 500) -> list[str]
```

Divide o texto em pedaços de no máximo `limit` caracteres, nos espaços sempre que possível; os
espaços nas junções são descartados. Se não houver espaço dentro de `limit`, a palavra é cortada
exatamente em `limit`. `chat` e `send_message` dividem textos longos do mesmo modo. Só é preciso
chamá-la à mão se você quiser enviar os pedaços com pausas ou para lugares diferentes.
