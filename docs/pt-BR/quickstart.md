[English](../en/quickstart.md) | [Русский](../ru/quickstart.md) | **Português (Brasil)**

# Início rápido

Em dez minutos você vai criar um bot no painel pessoal, dar a ele direitos em uma sala e
executar o primeiro script. Se algo der errado, veja [Erros e recusas](errors.md) e as
[Perguntas frequentes](faq.md).

## O que você precisa

| O quê | Para quê |
|---|---|
| Uma conta SukaRise com assinatura **PREMIUM** ativa | Bots são um recurso PREMIUM. Sem assinatura não dá para criar a chave de um bot, e uma chave existente deixa de conectar (volta a funcionar depois da renovação). |
| Uma sala onde você possa adicionar designers e moderadores | Um bot só entra em uma sala a convite do dono. |
| Python **3.13** ou mais novo | O SDK usa recursos de versões recentes da linguagem. |

## Passo 1. Instale o SDK

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
# Linux and macOS
source .venv/bin/activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
```

Instale o pacote a partir do repositório (ele é público, então não é preciso conta no GitHub):

```bash
pip install "sukarisebot @ git+https://github.com/fluxuscode/sukarise-bot-sdk.git"
```

Para uma versão específica, acrescente `@v0.2.0` (o nome de uma tag) ao endereço, ou baixe um
arquivo `.whl` na página de [Releases](https://github.com/fluxuscode/sukarise-bot-sdk/releases)
e instale com `pip install nome-do-arquivo.whl`. O pacote ainda não está no PyPI.

A única dependência é o `aiohttp`; ela é instalada automaticamente. Para verificar:

```bash
python -c "import sukarisebot; print(sukarisebot.__version__)"
```

## Passo 2. Crie um bot no painel pessoal

1. Abra o painel pessoal do SukaRise e vá à seção **"Bots"**.
2. Digite o nome do bot no campo **"Nome do bot"** e clique em **"Criar bot"**. O nome é o
   login do bot no jogo e é verificado como o apelido de um jogador: de 3 a 32 caracteres,
   letras latinas, dígitos e `_ . -`, e não pode estar em uso.
3. O painel mostra o **token** (uma string como `srbot_…`) e oferece copiá-lo. Guarde o token
   na hora: **ele não será mostrado de novo**. Se o perder, clique em **"Novo token"**: o
   antigo para de funcionar.
4. Na linha do bot aparece o **"login na sala"**: o nome que você escolheu. Você precisa dele
   no próximo passo.

Um bot novo já parece um personagem pronto: ele recebe uma aparência de acordo com o gênero do
dono (feminina ou masculina, e masculina se o perfil não informa o gênero), um fundo e uma
pose de perfil. A roupa do bot pode ser trocada depois, pelo código.

Uma conta pode ter até três bots. Os botões **"Desativar"**/**"Ativar"** param e retomam a
chave, e **"Excluir"** remove o bot para sempre.

> **O token é a senha do bot.** Não o publique em repositório, em chats nem em capturas de
> tela. Guarde-o em uma variável de ambiente ou em um arquivo que não vá para o git. Se o
> token vazar, emita um novo.

## Passo 3. Dê direitos ao bot na sala

Um bot é um participante da sala como uma pessoa e segue as mesmas regras.

1. Abra as configurações da sua sala.
2. Procure o bot pelo nome e adicione-o como **designer** da sala. Os seus próprios bots
   aparecem primeiro nas recomendações. Sem isso o bot não entra: o servidor responde que o
   bot precisa de direitos de designer.
3. Se o bot for **moderar** (`kick`, `ban`, `mute`) ou **teletransportar** pessoas,
   adicione-o também como **moderador**. O direito de "designer" não basta para isso.

Uma sala comporta até três bots ao mesmo tempo.

## Passo 4. Descubra o ID da sala

Um bot se conecta a uma sala pelo identificador dela: uma string como `room-ee3c8c43fb41e0b0`.
Você o informa em `room_id` ao iniciar.

## Passo 5. Escreva e execute o bot

Crie um arquivo `greeter.py`:

```python
from sukarisebot import Bot, Location, User


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Welcome, {user.username}!")


if __name__ == "__main__":
    Greeter().start()
```

É conveniente passar o token e a sala por variáveis de ambiente, para que não acabem no código.

Linux e macOS:

```bash
export SUKARISEBOT_TOKEN="srbot_..."
export SUKARISEBOT_ROOM_ID="room-..."
python greeter.py
```

Windows, PowerShell:

```powershell
$env:SUKARISEBOT_TOKEN = "srbot_..."
$env:SUKARISEBOT_ROOM_ID = "room-..."
python greeter.py
```

Windows, cmd:

```bat
set SUKARISEBOT_TOKEN=srbot_...
set SUKARISEBOT_ROOM_ID=room-...
python greeter.py
```

Se você precisar de um endereço de gateway diferente do padrão, defina `SUKARISEBOT_URL` (por
exemplo, para um servidor de testes). O token, a sala e o endereço também podem ser passados
como argumentos: `Greeter().start(token="…", room_id="…", url="…")`.

O bot aparece na sala como um jogador com a marca de bot, com o nome que você deu a ele, e
cumprimenta todo mundo que entra. Você pode pará-lo com `Ctrl+C`.

Também dá para executar um bot sem um script de inicialização próprio, com um comando:

```bash
python -m sukarisebot greeter:Greeter --room room-... --token srbot_...
```

(`greeter:Greeter` é "módulo:Classe"; o módulo é procurado no diretório atual. O comando
`sukarisebot greeter:Greeter` faz o mesmo.)

## E agora

- Ensine ao bot comandos e temporizadores: [Comandos, temporizadores e diálogos](commands.md).
- Veja todos os eventos que um bot pode escutar: [Manipuladores de eventos](handlers.md).
- Descubra o que um bot sabe fazer: [Referência da `BotAPI`](api.md).
- Soluções prontas para tarefas comuns: [Receitas](recipes.md).
- Entenda como tudo funciona por dentro: [Como o SDK funciona](architecture.md).

## Se o bot não conectar

As causas mais comuns:

| O que você vê | O que fazer |
|---|---|
| `ConnectionRefused: invalid or revoked bot token` | O token está errado, foi trocado pelo botão "Novo token", ou o bot foi desligado ou excluído. Verifique o token. |
| `ConnectionRefused: the bot needs designer rights in the room…` | Adicione o login do bot aos designers da sala (passo 3). |
| O bot não entra na sala, e o console repete avisos com o texto `the bot's owner needs an active PREMIUM subscription` | O PREMIUM do dono acabou. A recusa é temporária: o bot continua tentando sozinho e conecta quando a assinatura for renovada. |
| `ConnectionRefused` mencionando `HTTP 404` | Endereço de gateway errado, ou a API de bots não está ativada no servidor. O bot tenta de novo por 5 minutos seguidos e depois termina. Verifique `SUKARISEBOT_URL`. |

A tabela completa das recusas do servidor está em [Erros e recusas](errors.md). Para ver o que
acontece por dentro, ligue o log:

```python
import logging

logging.basicConfig(level=logging.INFO)
```
