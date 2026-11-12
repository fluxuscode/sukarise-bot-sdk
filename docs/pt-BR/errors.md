[English](../en/errors.md) | [Русский](../ru/errors.md) | **Português (Brasil)**

# Erros e recusas

Esta página reúne todas as exceções do SDK, o que significam e o que fazer com elas, além de uma
tabela das recusas que o servidor envia: ao conectar e em requisições individuais.

> **Idioma das mensagens.** Os textos das exceções do SDK estão em russo. Os textos das recusas
> que o servidor envia (`error.message`) estão em inglês, como no protocolo oficial. Abaixo,
> cada um deles vem com uma explicação e um conselho.

## Hierarquia das exceções

Todos os erros do SDK herdam `SukaRiseError`, então `except SukaRiseError` pega todos eles.

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

| Exceção | Atributos | Quando ocorre | O que fazer |
|---|---|---|---|
| `InvalidArgument` | — | texto vazio, reação/barra de ouro/ação desconhecida, coordenada fora de ±1000, número de assento fora de 0…255, identificador ou etiqueta longo demais, roupa que viola as regras, nome de comando errado. **A requisição não foi enviada.** | Corrija a chamada no seu código. É um erro de programação, não uma falha de conexão. |
| `ResponseError` | `message` | O servidor recusou uma requisição: sem direitos, a pessoa não está na sala, o servidor não suporta a ação. A conexão continua funcionando. | Leia `error.message` e, se necessário, responda ao jogador. Veja a tabela abaixo. |
| `RateLimited` | `message` | O servidor recusou por causa do limite de frequência, e várias novas tentativas do SDK não resolveram. A requisição **não foi executada**. Herda `ResponseError`. | Envie requisições com menos frequência; tente de novo mais tarde. Mais na seção "Limite de frequência" abaixo. |
| `RequestTimeout` | — | O servidor não respondeu em 10 segundos. A requisição pode ter sido executada. | Se a ação não puder ser repetida às cegas (gorjeta, compra), verifique antes o resultado (`await api.gold()`). |
| `NotConnected` | — | `bot.api` usado fora de um bot em execução; requisição durante a reconexão; queda no meio de uma requisição. | Esperar a conexão; nos temporizadores, verificar `self.connected`. |
| `ConnectionRefused` | `message`, `do_not_reconnect` | O servidor não aceitou a conexão ou encerrou a sessão. Sai de `run`/`start`. | Veja a tabela "Recusas ao conectar" abaixo. |
| `ProtocolError` | — | O servidor enviou um quadro que o SDK não entende. O SDK ignora um quadro isolado e o registra no log. | Em geral nada: relate o problema se ele se repetir. |

## Como tratar

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

Se uma exceção não for capturada, ela não derruba o bot: o SDK a entrega ao
[`on_error`](handlers.md#on_error) e o bot continua funcionando.

## Limite de frequência

O servidor limita a frequência das requisições por categoria, e o SDK mantém os mesmos
contadores, então quase sempre espera a própria vez. Mas atrasos de rede podem comprimir os
intervalos entre as requisições, e o servidor pode concluir uma fração de segundo antes do SDK
que o orçamento acabou. Ele então responde `Rate limit exceeded for <category> requests`
**antes** de executar a requisição. Antes, essa recusa virava um `ResponseError` na hora. Agora o
SDK repete a requisição até três vezes, com uma pausa de um segundo (é seguro: a requisição não
foi executada), e só depois lança `RateLimited`. A exceção herda `ResponseError`, então um
`except ResponseError` já existente continua funcionando.

## Recusas ao conectar

A exceção `ConnectionRefused` sai de `run()`/`start()` quando o bot parou e não pode continuar.
A coluna "SDK" diz o que o SDK faz:

- **repete**: a palavra do servidor é "a recusa é temporária" (`do_not_reconnect = False`): um
  bot com `reconnect=True` não termina, mas tenta de novo com uma pausa crescente de até 30
  segundos;
- **termina**: a recusa é definitiva (`do_not_reconnect = True`): `run()` lança
  `ConnectionRefused`.

Com `reconnect=False` a exceção é lançada nos dois casos, inclusive numa recusa HTTP temporária
(por exemplo, 503); dá para distingui-los por `error.do_not_reconnect`.

| Texto do servidor | O que significa | O que fazer | SDK |
|---|---|---|---|
| `invalid or revoked bot token` | O token está errado, foi trocado pelo botão "Novo token", o bot está desligado ou foi excluído, ou o dono está bloqueado. | Verifique o token; se preciso, emita um novo no painel. | termina |
| `the bot's owner needs an active PREMIUM subscription` | O dono do bot não tem assinatura PREMIUM ativa. | Renove o PREMIUM; o bot conecta sozinho. | repete |
| `the bot needs designer rights in the room: add the bot's username as a designer in the room settings` | O bot não é designer da sala. | Adicione o login do bot aos designers da sala. | termina |
| `the room does not exist` | Não existe sala com esse ID. | Verifique o `room_id`. | termina |
| `the room is full` | Não há vaga na sala. | Libere uma vaga ou escolha outra sala. | termina |
| `the room already holds the maximum number of bots` | A sala já tem três bots. | Desconecte um dos bots. | termina |
| `bots cannot join this 3D room: the 3D world service is not available to bots on this server` | Esta sala 3D não está disponível para bots no servidor. | Use uma sala 2D. | termina |
| `bots are not enabled on this server` | A API de bots está desligada no servidor. | Fale com o administrador do servidor. | termina |
| `A valid room-id header is required` | `room_id` está vazio ou tem caracteres não permitidos. | Verifique o `room_id`. | termina |
| `This bot connected from another place` | O mesmo token foi conectado em outro lugar; a nova conexão vence. | Execute um bot por token. | termina |
| `the room is not ready, try again shortly` | A sala ainda não está pronta (por exemplo, um mundo 3D está iniciando). | Nada: o SDK tenta de novo. | repete |
| `The room could not be joined right now` | Um erro temporário na entrada. | Nada: o SDK tenta de novo. | repete |
| `Authentication is temporarily unavailable` | Um erro temporário na verificação do token. | Nada: o SDK tenta de novo. | repete |
| `The server is restarting` | O servidor está reiniciando. | Nada: o SDK tenta de novo. | repete |
| HTTP 404 | Esse endereço não existe: um `SUKARISEBOT_URL` errado, ou a API de bots não está ligada ao servidor web. Enquanto o servidor é atualizado, a rota pode sumir por um instante, por isso o SDK continua tentando, mas por no máximo 5 minutos seguidos. | Verifique o endereço. | repete e depois termina |
| HTTP 400, 401, 403 | A requisição foi rejeitada no nível do HTTP. | Verifique o endereço e o token. | termina |
| HTTP 503 `too many bot connections` | O gateway está sobrecarregado de conexões. | Nada: o SDK tenta de novo. | repete |

O SDK também reconecta depois de uma queda de rede e depois de qualquer outra resposta HTTP
temporária.

## Recusas de requisições individuais (`ResponseError`)

Textos típicos que um bot pode ver em `error.message`:

| Texto do servidor | O que significa e o que fazer |
|---|---|
| `Rate limit exceeded for <category> requests` | O limite de frequência foi excedido. O SDK espera a vez e repete essa recusa sozinho; ela sai como `RateLimited`. |
| `The message is empty` / `The message is longer than 500 characters` | Uma fala vazia ou longa demais (o SDK divide as longas sozinho). |
| `That user is not in this room` / `That user does not exist` | O destinatário de um sussurro, reação ou gorjeta não está na sala. |
| `The bot is muted in this room` / `The bot is banned from this room` | O bot foi silenciado ou banido. |
| `The bot cannot whisper this user` / `The whisper could not be sent` / `This user is not accepting whispers from the bot` | O sussurro não foi entregue. |
| `The bot cannot walk there` / `The destination is not on the floor of this room` / `The destination is not a point in the room` | O ponto de `move_to` ou `teleport_user` não é alcançável. |
| `That seat is not in this room` | Não existe esse assento para `sit_on`. |
| `Teleporting a user needs moderator rights in the room` | O teletransporte exige direitos de moderador. |
| `That seat is taken` | O assento está ocupado por uma pessoa ou outro bot. Escolha outro. |
| `The bot is already sitting` | O bot já está sentado. Primeiro levante-o, mandando-o andar para algum lugar (`move_to`). |
| `The bot could not reach that seat` | Em um mundo 3D o bot não chegou ao assento em 8 segundos e ficou de pé. Escolha outro assento ou um ponto mais perto. |
| `The bot sat on another seat, and that one is not reachable` | Em um mundo 3D o mundo sentou o bot em outro assento, e o escolhido é inalcançável. O bot agora está sentado em outro assento. |
| `That user was moved a moment ago` | Em um mundo 3D uma pessoa só pode ser movida uma vez a cada 0,6 s. Repita depois de um segundo. |
| `The bot is not in this room` / `The bot is no longer in the room` | O bot ainda não entrou na sala ou já saiu dela. Espere a entrada. |
| `The emote is unknown` / `The bot cannot perform that emote` | Esse emote não existe ou o bot não pode executá-lo (um pago, sem PREMIUM no dono). |
| `This emote needs a partner, and a bot cannot give one yet` | Emotes em par não estão disponíveis para bots. |
| `Unknown reaction` | Uma reação desconhecida. |
| `That gold bar is not available` / `That user cannot be tipped` / `The recipient cannot hold more` / `Tips are unavailable right now` | A gorjeta não foi enviada. Falta de ouro não é recusa: `tip` retorna `False`. |
| `That item does not exist` / `That item is not sold to bots` / `That item is not available right now` / `That item is only for players with SukaRise PREMIUM` / `Bots can buy only items sold for gold` / `The bot cannot hold more items` / `The shop is unavailable right now` | A compra é impossível. Falta de ouro não é recusa: `buy_item` retorna `False`. |
| `The bot's owner needs an active PREMIUM subscription to change the bot's outfit` | Trocar a roupa é proibido sem PREMIUM no dono. |
| `Unknown item: …` / `The outfit is empty` / `The outfit has too many items` / `The outfit has an item without an id` / `The outfit is missing a … item` / `The outfit wears two … items; a bot wears one of each basic part` / `The outfit does not cover the body…` | A roupa não passou na verificação do servidor. |
| `Bots cannot change room privileges; the room owner does that` / `Changing room privileges from bots is not available yet` | `set_privileges` sempre recusa: só o dono e a equipe mudam direitos em uma sala. |
| `The conversation does not exist` / `Bots take part in direct conversations only` / `The bot cannot write to this conversation` | A conversa não existe, não é direta, ou o bot não pode escrever nela. |
| `The bot has no open conversation with these users: bots answer people who wrote first` | `send_bulk_message`: o bot escreve só para quem já escreveu para ele. |
| `This request is not supported on this server` | O servidor não suporta esta operação. |
| `Internal error` | Um erro interno do servidor. |

Algumas ações **sempre** são recusadas aos bots no SukaRise: `set_privileges`, chat de voz,
mochila, serviços pagos da sala, levar pessoas para outra sala, mensagens de mídia. O SDK não
tem métodos para elas, exceto `set_privileges`.

## Log

O SDK escreve em um logger chamado `sukarisebot`. Para ver reconexões, recusas e erros nos
manipuladores, ligue a saída:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
```

Níveis: `INFO`: reconexões; `WARNING`: conexão perdida, recusas temporárias, quadros e eventos
descartados; `ERROR`: exceções no seu código (com o traceback). O token nunca vai para o log.
