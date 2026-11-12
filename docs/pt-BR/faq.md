[English](../en/faq.md) | [Русский](../ru/faq.md) | **Português (Brasil)**

# Perguntas frequentes

## O bot conectou, mas não reage às mensagens

Verifique nesta ordem:

1. **Existe um manipulador ou um comando.** O bot só ouve o que tem um manipulador sobrescrito
   (`on_chat`, `on_user_join` …) ou um comando declarado. Veja
   [Manipuladores](handlers.md).
2. **Os comandos começam com `!`.** `!roll` é um comando, `roll` não é.
3. **Um comando só para o dono** (`owner_only=True`) responde com uma recusa a todos, exceto ao
   dono da *sala*.
4. **O bot está mesmo na sala.** Ele deve aparecer na lista de pessoas com o nome que você deu a
   ele. Se não, ligue o log (`logging.basicConfig(level=logging.INFO)`) e procure a causa na
   [tabela de recusas](errors.md#recusas-ao-conectar).
5. **Um erro no seu código.** As exceções não derrubam o bot; elas vão para `on_error` e para o
   log `sukarisebot`: ligue o log para vê-las.

## O `bot.room` mostra as pessoas no lugar errado

A lista da sala sempre vê as pessoas entrando e saindo (exceto no modo "sala limpa"), então
quem saiu some dela e quem entrou aparece sozinho. Já os movimentos só chegam se `on_user_move`
for sobrescrito (o corpo pode ficar vazio): sem ele, a posição de uma pessoa na lista é onde ela
estava ao entrar. Mais em [Ferramentas](tools.md#a-lista-da-sala-botroom). Você pode atualizar a
lista por completo chamando `await self.refresh_room()`. Se quem saiu ainda continua na lista,
verifique se o modo "sala limpa" está ligado e se você usa um SDK anterior à 0.3.0: nele, as
entradas e saídas só eram consideradas se `on_user_join` e `on_user_leave` fossem sobrescritos.

## O `wait_for` espera até o tempo limite e não recebe nada

- O evento de que você precisa deve chegar ao bot. O chat e as entradas e saídas sempre chegam,
  e para qualquer outro evento sobrescreva o manipulador dele (um vazio basta).
- O `check` precisa retornar `True` para o evento de que você precisa; verifique a condição.
- Sempre defina um `timeout`. Veja [Diálogos](commands.md#diálogos-wait_for).

## O bot "congela" enquanto espera a resposta de um jogador

Os manipuladores executam um de cada vez, e um comando à espera ocupa a fila. Isso é proposital
(assim não são necessárias travas no código). Para diálogos com vários jogadores ao mesmo tempo,
inicie o diálogo como uma tarefa separada: a receita está em
[Diálogos com vários jogadores ao mesmo tempo](commands.md#diálogos-com-vários-jogadores-ao-mesmo-tempo).

## Posso usar `requests`, `time.sleep` e outras chamadas bloqueantes?

Não. Uma chamada bloqueante para todo o laço de eventos e o bot deixa de ler o socket. Use
`await asyncio.sleep(...)`, `bot.http` (aiohttp) ou `await asyncio.to_thread(function)` para
trabalho síncrono pesado.

## Quantos bots posso criar e manter em uma sala?

Até **três bots ativos por conta** e até **três bots ao mesmo tempo em uma sala**. Há também um
limite geral de chaves emitidas por conta (o painel avisa se ele acabou). Para criar e executar
um bot, o dono precisa ter uma assinatura PREMIUM ativa.

## O que acontece se o PREMIUM acabar?

A chave não é excluída. O bot não consegue conectar até a assinatura ser renovada, e um bot já
conectado recebe uma recusa temporária na próxima conexão. O SDK continua tentando sozinho, então
depois da renovação o bot volta sem a sua participação.

## Como obtenho o ouro que o bot ganhou?

O bot recebe gorjetas em ouro na própria carteira (`await self.api.gold()`). O dono retira o ouro
acumulado no painel pessoal: no cartão do bot há o botão **"Sacar gold"**. O bot também pode
gastar o próprio ouro: `api.tip(...)` e `api.buy_item(...)`.

## Por que o bot não escreve primeiro nas mensagens diretas?

É de propósito: o bot **responde** nas conversas em que já está, e quem começa a conversa é a
pessoa. O `send_bulk_message` também escreve só para quem já escreveu ao bot.

## O bot funciona em salas 3D?

Quase tudo. Em 3D funcionam: chat, sussurros, andar, emotes, reações, sentar em móveis,
teletransporte, moderação, gorjetas (dar), a lista de pessoas, mensagens diretas, a carteira, o
guarda-roupa e a roupa. O bot recebe as caminhadas e os emotes das pessoas. As reações das
pessoas não são enviadas pelo cliente 3D, então o bot não as recebe lá. O bot recebe as gorjetas
das pessoas também em 3D. Um resumo está na [Referência das ações](api.md#resumo). Se o servidor
não suporta 3D para bots, a conexão é recusada com um texto claro.

## Posso executar vários bots em um único processo?

Sim: cada objeto `Bot` tem o seu próprio engine e a sua própria conexão.

```python
import asyncio

from sukarisebot import Bot


class First(Bot):
    pass


class Second(Bot):
    pass


async def main() -> None:
    await asyncio.gather(
        First().run(token="srbot_1...", room_id="room-1..."),
        Second().run(token="srbot_2...", room_id="room-2..."),
    )


asyncio.run(main())
```

Se um dos bots terminar com um erro, o `gather` o relança; para que os outros continuem
funcionando, envolva cada início em seu próprio `try/except` ou use `return_exceptions=True`.

## Como mantenho um bot em execução em um servidor?

Execute o script como um serviço do sistema, para que ele inicie depois de uma reinicialização e
reinicie depois de uma falha. Um exemplo para Linux (`/etc/systemd/system/sukarisebot.service`):

```ini
[Unit]
Description=SukaRise bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/mybot
EnvironmentFile=/etc/mybot.env
ExecStart=/opt/mybot/.venv/bin/python -m sukarisebot mybot:MyBot
Restart=on-failure
RestartSec=5
User=mybot

[Install]
WantedBy=multi-user.target
```

O `/etc/mybot.env` contém `SUKARISEBOT_TOKEN=…` e `SUKARISEBOT_ROOM_ID=…`; as permissões do
arquivo devem ser só para o usuário do serviço. O SDK reconecta sozinho depois de quedas de
conexão, e o `Restart=on-failure` reinicia o processo depois de uma saída inesperada.

## O que o bot faz quando o servidor reinicia ou a conexão cai?

O bot conecta de novo sozinho enquanto `Bot.run()` tiver sido chamado com `reconnect=True` (o
padrão). As pausas crescem de 0,5 s até 30 s com uma variação aleatória. Depois de cada nova
conexão `on_start` é chamado, então a saudação e as assinaturas são enviadas de novo. Um servidor
que fica em silêncio por mais de três intervalos de keepalive (cerca de um minuto) é dado como
perdido: o bot fecha a conexão e conecta de novo. As recusas definitivas, depois das quais o bot
não tenta de novo: um token errado (401, 403), uma requisição errada (400) e uma conexão de outro
lugar. O bot repete uma resposta HTTP 404, porque a rota pode estar indisponível enquanto o
servidor é atualizado, mas por no máximo 5 minutos seguidos: se o gateway responder 404 durante
todo esse tempo, o bot termina com `ConnectionRefused` e pede que você verifique o endereço.

## Como troco o token?

No painel clique em **"Novo token"** no cartão do bot: o token antigo para de funcionar na hora.
Coloque o novo e reinicie o bot. Um bot em execução com o token antigo recebe, na próxima
conexão, a recusa "invalid or revoked bot token".

## Por que vejo a recusa "Rate limit exceeded"?

O servidor limita a frequência das requisições por categoria, e o SDK normalmente espera a
própria vez. Se o servidor mesmo assim recusar (atrasos de rede fizeram os contadores se
afastarem), o SDK repete a requisição até três vezes e depois lança `RateLimited`. Se você o vê
com frequência, chame os métodos de uma mesma categoria com menos frequência (por exemplo, o
`chat` permite 20 a cada 10 segundos) ou junte as falas. Veja
[Erros e recusas](errors.md#limite-de-frequência).

## Por que os textos de recusa do servidor estão em inglês?

O protocolo é compatível com o SDK oficial do Highrise, e o gateway envia os textos de recusa em
inglês. As traduções das recusas típicas estão em
[Erros e recusas](errors.md#recusas-de-requisições-individuais-responseerror). Os textos das
exceções do próprio SDK e as frases padrão do bot estão em russo; as frases do bot podem ser
trocadas com [`Phrases`](commands.md#o-que-o-bot-diz-sozinho-phrases).

## Como paro o bot?

Pelo console: `Ctrl+C`. Pelo código: `await self.stop()` (por exemplo, em um comando para o
dono); `run()`/`start()` retornam depois disso.

## Onde vejo o que o bot enviou e recebeu?

Um bot em execução não escreve cada requisição e evento no log, para não poluí-lo. O `DEBUG`
mostra apenas os quadros ignorados de tipos desconhecidos. Para ver todas as requisições do bot,
execute-o no [`Harness`](testing.md): ele grava cada ação em `harness.requester.sent`. Para uma
conexão real, acrescente registros de log nos seus próprios manipuladores.
