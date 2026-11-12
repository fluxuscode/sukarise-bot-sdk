[English](README.md) | [Русский](README.ru.md) | **Português (Brasil)**

# SukaRiseBot

**SDK Python** assíncrono e totalmente tipado **para bots do SukaRise**. O bot entra em uma
sala por websocket, lê o chat e os eventos, anda, fala, modera, recebe gorjetas, responde a
mensagens diretas e cuida da própria economia com uma carteira. Tudo isso com Python comum,
com dicas no editor e tipos estritos.

```python
import random

from sukarisebot import Bot, Context, Location, User, command


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Welcome, {user.username}!")

    @command("roll", cooldown=(3, 60.0), description="roll a die")
    async def roll(self, ctx: Context) -> None:
        await ctx.reply(f"@{ctx.user.username} rolled {random.randint(1, 6)}")


if __name__ == "__main__":
    Greeter().start()
```

## Recursos

- **Chat e conversa:** falas públicas, sussurros, um canal oculto entre bots.
- **Movimento:** andar, sentar em móveis, teletransportar jogadores (com direitos de moderador).
- **Moderação:** `kick`, `ban`, `unban`, `mute`, leitura dos direitos na sala.
- **Gorjetas:** o bot recebe gorjetas em ouro na própria carteira e o dono as retira no painel
  pessoal; o bot também pode dar gorjetas e comprar itens com o próprio ouro.
- **Mensagens diretas:** o bot recebe e trata mensagens diretas e responde a elas.
- **Aparência:** o bot troca de roupa e pode vestir a roupa do dono com o comando `myoutfit`.
- **Comandos, temporizadores e diálogos:** `@command`, `@every`, `wait_for`.
- **Dados entre execuções:** `JsonStore` com gravação atômica.
- **Testes sem servidor:** o `Harness` testa o bot em memória.
- **Tipos estritos e dicas:** `py.typed`, uma descrição para cada nome público, `mypy --strict`
  e `pyright` no modo `strict`.

## Requisitos

- Python **3.13** ou mais novo;
- uma conta SukaRise com assinatura **PREMIUM** ativa (a do dono do bot);
- a dependência `aiohttp` é instalada automaticamente.

## Instalação

O repositório é público: não é preciso conta no GitHub nem o `gh`. O pacote ainda não está no
PyPI, então instale a partir do repositório:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install "sukarisebot @ git+https://github.com/fluxuscode/sukarise-bot-sdk.git"
```

Para uma versão específica, acrescente `@v0.2.0` (o nome de uma tag) ao endereço, ou baixe um
arquivo `.whl` na página de [Releases](https://github.com/fluxuscode/sukarise-bot-sdk/releases)
e instale com `pip install nome-do-arquivo.whl`.

## Início rápido

1. No painel pessoal do SukaRise abra a seção **"Bots"**, crie um bot e guarde o token
   (`srbot_…`): ele é mostrado uma única vez.
2. Nas configurações da sua sala procure o bot pelo nome e adicione-o como **designer** (e como
   **moderador**, se o bot for moderar).
3. Inicie o bot, informando o token e o ID da sala:

   ```bash
   export SUKARISEBOT_TOKEN="srbot_..."
   export SUKARISEBOT_ROOM_ID="room-..."
   python examples/greeter.py
   ```

Passo a passo, com uma tabela de solução de problemas, está no **[Início rápido](docs/pt-BR/quickstart.md)**.

## Documentação

A documentação existe em três idiomas: [English](docs/en/README.md),
[Русский](docs/ru/README.md), [Português (Brasil)](docs/pt-BR/README.md). Abaixo estão as
páginas da versão em português do Brasil.

| Página | Sobre o quê |
|---|---|
| [Início rápido](docs/pt-BR/quickstart.md) | Instalação, token, direitos, primeira execução |
| [Como o SDK funciona](docs/pt-BR/architecture.md) | Como tudo funciona por dentro |
| [Manipuladores de eventos](docs/pt-BR/handlers.md) | Todos os métodos `on_...` |
| [Referência da `BotAPI`](docs/pt-BR/api.md) | Todas as ações do bot |
| [Comandos, temporizadores e diálogos](docs/pt-BR/commands.md) | `@command`, `@every`, `wait_for` |
| [Modelos de dados](docs/pt-BR/models.md) | `User`, `Position`, eventos e mais |
| [Erros e recusas](docs/pt-BR/errors.md) | Exceções e recusas do servidor |
| [Testes](docs/pt-BR/testing.md) | `Harness` |
| [Ferramentas](docs/pt-BR/tools.md) | Lista da sala, `JsonStore`, `bot.http`, CLI |
| [Receitas](docs/pt-BR/recipes.md) | Soluções prontas |
| [Protocolo](docs/pt-BR/protocol.md) | Quadros no nível da rede |
| [Editores e dicas](docs/pt-BR/editors.md) | PyCharm, VS Code, mypy, pyright |
| [Perguntas frequentes](docs/pt-BR/faq.md) | Solução de problemas |

Bots de exemplo prontos estão no diretório [`examples/`](examples/): um que dá boas-vindas, um
de dados com comandos, um quiz que espera as respostas, um de "sala limpa", um que agradece
gorjetas, um registro de visitas e um bot que coleta gorjetas. O histórico de mudanças está em
[CHANGELOG.pt-BR.md](CHANGELOG.pt-BR.md).

## O que funciona e o que não funciona

| Recurso | Salas 2D | Salas 3D |
|---|---|---|
| Chat, sussurros, canal entre bots | sim | sim |
| Entrada e saída de pessoas | sim | sim |
| Eventos de movimento, emotes e reações das pessoas | sim | caminhadas e emotes das pessoas; o cliente 3D não envia as reações das pessoas |
| Andar (`move_to`) | sim | sim |
| Emotes | sim | sim |
| Reações, sentar em móveis | sim | sim |
| Teletransporte e moderação (exigem direitos de moderador) | sim | sim |
| Gorjetas (receber e dar) | sim | sim |
| Mensagens diretas | sim | sim |
| Carteira, guarda-roupa, roupa, compras com ouro | sim | sim |

Indisponível para bots no servidor do SukaRise: emotes em par, troca de direitos em uma sala
(`set_privileges` sempre recusa), chat de voz, mochila, serviços pagos da sala, levar pessoas
para outra sala, mensagens de mídia.

## Idioma dos textos do SDK

As descrições no código (docstrings), os textos das exceções do SDK e as frases padrão do bot
(a recusa a quem não é dono, "aguarde", `!help`) estão em russo. As frases do bot são trocadas
em uma linha: `Bot.phrases = Phrases(...)` (veja
[Comandos, temporizadores e diálogos](docs/pt-BR/commands.md)). Os textos de recusa do servidor
chegam em inglês e são repassados como estão.

## Origem do código

O SDK `sukarisebot` foi feito segundo o princípio de clean-room design. Foi escrito de forma
independente para o protocolo do SukaRise e não tem relação com a Pocket Worlds nem com o seu
projeto Highrise: não é produto deles e não é endossado por eles. Os nomes dos campos e o
formato dos quadros coincidem com o SDK Python oficial do Highrise, para que o código possa ser
portado.

## Desenvolvimento

```bash
pip install -e ".[test]"
python -m pytest        # tests run against a real websocket stand-in gateway (tests/fake_gateway.py)
python -m ruff check .  # linter
python -m mypy          # strict type check
python -m pyright       # strict type check
```

Os testes também executam os programas de `examples/` e os trechos de código da documentação,
por isso a documentação não se afasta do código. Eles ainda garantem que os três idiomas da
documentação tenham a mesma estrutura: páginas, títulos, tabelas, links e blocos de código.
