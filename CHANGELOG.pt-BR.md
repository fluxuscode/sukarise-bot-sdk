[English](CHANGELOG.md) | [Русский](CHANGELOG.ru.md) | **Português (Brasil)**

# Histórico de mudanças

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). As versões seguem o
[versionamento semântico](https://semver.org/lang/pt-BR/). Enquanto a versão principal for 0,
mudanças de comportamento também podem vir em versões menores; elas estão sempre listadas aqui.

## Não lançado

## 0.3.0 — 2026-11-12

### Corrigido

- As etiquetas de uma mensagem de canal: o servidor conta o tamanho delas em **bytes** (até 32)
  enquanto o SDK contava caracteres, então uma etiqueta de 17 letras cirílicas passava na
  verificação do SDK e era recusada pelo servidor. O SDK agora conta bytes.
- Verificações antes do envio contra os limites do servidor: o número do assento em `sit_on` é um
  inteiro de 0 a 255, os identificadores de um emote (até 96 bytes), de um móvel e de uma conversa
  (até 128), de um item em `buy_item` (até 256), e uma roupa em `wear` tem no máximo 64 itens. Uma
  chamada errada lança `InvalidArgument` na hora, em vez de uma recusa do servidor.
- `wear` e `outfit_problems` recusavam por engano roupas em que o tipo de um item não se vê pelo
  identificador: o servidor determina a categoria pelo catálogo, e para ele
  `bag-n_elite2026dazzledbrows` é uma sobrancelha. Itens com identificadores `bag-…` agora podem
  suprir uma parte do corpo que falta ou cobrir o corpo, e `wear(await api.outfit_of(...))`
  funciona.
- `reconnect=False` terminava em silêncio diante de uma recusa HTTP temporária da conexão (por
  exemplo, 503); agora é lançado um `ConnectionRefused` com `do_not_reconnect=False`.
- O comando `sukarisebot module:Class` não achava o módulo no diretório atual (só o
  `python -m sukarisebot` achava); agora acha.
- A tabela de chamadas do `cooldown` crescia a cada jogador novo; os registros de jogadores que não
  escrevem há muito tempo agora são esquecidos.

### Alterado

- Uma recusa do servidor por limite de frequência (`Rate limit exceeded for … requests`) chega
  antes de a requisição ser executada, então o SDK repete a requisição até três vezes, com uma
  pausa de um segundo. Se isso não ajudar, é lançada a nova `RateLimited`, uma subclasse de
  `ResponseError`: um `except ResponseError` existente funciona como antes.
- Uma resposta HTTP 404 ao conectar continua sendo repetida, mas por no máximo 5 minutos seguidos
  (`Engine(not_found_grace=…)`): depois disso, um `ConnectionRefused` com a dica de verificar o
  endereço. Antes, um endereço errado era repetido sem fim.
- As entradas e saídas das pessoas sempre chegam ao bot, exceto no modo "sala limpa", então o
  `bot.room` continua correto mesmo sem `on_user_join` e `on_user_leave`. Os movimentos continuam
  chegando só quando `on_user_move` é sobrescrito.
- O `--log-level` na linha de comando aceita só `DEBUG`, `INFO`, `WARNING` e `ERROR`; qualquer
  outro valor dá uma mensagem de erro de uso, em vez de um traceback.
- `Location` e `Event` são declarados como `X | Y` em vez de `typing.Union`; nada muda para o
  código que os desmonta com `isinstance` ou `match`.

### Adicionado

- A exceção `RateLimited`, e os parâmetros `not_found_grace` e `rate_limit_pause` do `Engine`.
- Os testes em `tests/test_hardening.py` para tudo o que está listado acima; os testes ficaram
  mais rápidos (de 90 para cerca de 17 segundos: o simulador do gateway fecha seus sockets ao
  encerrar).
- Verificação de código (`ruff`), construção e verificação do pacote, CI no GitHub Actions com
  Python 3.13 e 3.14.
- Metadados do pacote: links do projeto, classificadores para os idiomas da documentação, uma
  descrição em inglês.
- Documentação em três idiomas: inglês (o principal), russo e português do Brasil; o
  `tests/test_docs.py` verifica que as páginas, os títulos, as tabelas, os links e os blocos de
  código são iguais nos três.

### Documentação

- Instalação: o repositório é público, então não é preciso conta no GitHub nem o `gh`; o pacote
  ainda não está no PyPI. Trechos desatualizados foram corrigidos: em diagramas e descrições, uma
  resposta HTTP 404 era tratada como definitiva.
- A seção "Idioma dos textos do SDK": as descrições no código, as exceções e as frases padrão do
  bot estão em russo.

## 0.2.0 — 2026-10-14

- Reconexão: depois que o servidor reinicia, o bot espera e conecta de novo; `on_start` é chamado a
  cada conexão, e `bot.connected` é `False` enquanto ele espera.
- Um servidor que fica em silêncio por mais de três intervalos de keepalive (cerca de um minuto) é
  dado como perdido: o bot fecha a conexão e conecta de novo. Antes, o bot podia travar em uma
  conexão assim.
- Uma resposta HTTP 404 ao conectar não é mais definitiva: o bot tenta de novo, porque a rota pode
  estar indisponível enquanto o servidor é atualizado. As recusas definitivas continuam as mesmas:
  400, 401, 403 e "conectado de outro lugar".
- O endereço padrão do gateway: `wss://production-portal-refb.sukarise.ru/web/botapi`.
- Instalação a partir de uma release do GitHub: o arquivo `sukarisebot-0.2.0-py3-none-any.whl` na
  página da release.
- Em salas 3D (mundos) funcionam reações, sentar em móveis, teletransporte, moderação (kick, ban,
  unban, mute) e gorjetas do bot (dar). Antes, o servidor as recusava.
- Em 3D o bot ouve as caminhadas e os emotes das pessoas: `on_user_move` e `on_emote` disparam lá
  também.
- Um emote com destinatário verifica que o destinatário está na sala, em 3D e em 2D; como antes, o
  destinatário não é passado no evento.
- As reações das pessoas não são enviadas pelo cliente 3D, então `on_reaction` não dispara em 3D.
  O bot recebe as gorjetas das pessoas em salas 3D como em 2D: `on_tip` dispara lá também.
- As recusas "…is not available in 3D rooms yet" para reações, sentar, teletransporte, moderação e
  gorjetas não são mais dadas; servidores antigos ainda podem enviá-las.
- Novas recusas: `That seat is taken`, `The bot is already sitting`, `The bot could not reach that seat`,
  `That user was moved a moment ago`, `The bot is not in this room`.

## 0.1.0

A primeira versão do SDK.

- A classe `Bot` com manipuladores `on_...`, comandos (`@command`), temporizadores (`@every`) e
  espera por uma resposta (`wait_for`).
- As ações da `BotAPI`: chat e sussurros, um canal oculto entre bots, emotes e reações, andar,
  sentar, teletransporte, moderação, gorjetas e compras com o ouro do bot, mensagens diretas, a
  carteira, o guarda-roupa e a roupa.
- A lista da sala `bot.room`, o modo "sala limpa", o armazenamento `JsonStore`, o cliente HTTP
  compartilhado `bot.http`.
- Testes sem servidor (`Harness`) e início pela linha de comando (`python -m sukarisebot`).
- Tipagem estrita (`py.typed`, `mypy --strict`, `pyright` strict), descrições de todas as classes,
  métodos e campos públicos em russo, documentação no diretório `docs/`.
- Os textos das exceções do SDK e as frases padrão do bot (a recusa a quem não é dono, "aguarde",
  `!help`) estão em russo; as frases do bot são trocadas com `Bot.phrases = Phrases(...)`.
