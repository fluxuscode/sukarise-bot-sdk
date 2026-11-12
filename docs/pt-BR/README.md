[English](../en/README.md) | [Русский](../ru/README.md) | **Português (Brasil)**

# Documentação do SukaRiseBot

O SukaRiseBot é um SDK Python assíncrono e totalmente tipado para bots do SukaRise. Esta
documentação foi escrita para quem quer não só executar um bot, mas também entender como tudo
funciona.

## Por onde começar

Se você está aqui pela primeira vez, leia nesta ordem:

1. **[Início rápido](quickstart.md)**: criar um bot no painel pessoal, dar a ele direitos em
   uma sala e executar o primeiro script.
2. **[Manipuladores de eventos](handlers.md)**: o que o bot pode escutar: chat, entradas,
   gorjetas, mensagens diretas e mais.
3. **[Referência da `BotAPI`](api.md)**: o que o bot sabe fazer: falar, andar, moderar, dar
   gorjetas, responder a mensagens diretas.
4. **[Comandos, temporizadores e diálogos](commands.md)**: `!comandos`, tarefas periódicas e
   perguntas que esperam uma resposta.

## Todas as páginas

| Página | Sobre o quê |
|---|---|
| [Início rápido](quickstart.md) | Instalação, token, direitos na sala, primeira execução |
| [Como o SDK funciona](architecture.md) | Como o SDK é construído por dentro: camadas, ciclo de vida, ordem dos eventos, limites, reconexão |
| [Manipuladores de eventos](handlers.md) | Todos os métodos `on_...`: quando são chamados e o que recebem |
| [Referência da `BotAPI`](api.md) | Todas as ações do bot: parâmetros, limites, exceções |
| [Comandos, temporizadores e diálogos](commands.md) | `@command`, `@every`, `wait_for`, `Phrases`, o estado do bot |
| [Modelos de dados](models.md) | `User`, `Position`, `Item`, eventos e outras classes imutáveis |
| [Erros e recusas](errors.md) | As exceções do SDK e uma tabela de recusas do servidor com tradução e conselhos |
| [Testes sem servidor](testing.md) | `Harness`: testar um bot sem conectar |
| [Ferramentas](tools.md) | A lista da sala, "sala limpa", `JsonStore`, `bot.http`, a roupa, a linha de comando |
| [Receitas](recipes.md) | Soluções prontas para tarefas comuns |
| [Protocolo](protocol.md) | Quadros, requisições e eventos no nível da rede |
| [Editores e dicas](editors.md) | PyCharm, VS Code, mypy e pyright: como ativar as dicas e os tipos estritos |
| [Perguntas frequentes](faq.md) | Solução de problemas comuns |

## Princípios do SDK

- **Tipagem estrita.** Todas as funções e dados públicos são tipados; o SDK passa no
  `mypy --strict` e no `pyright` no modo `strict`. Os dados que você recebe são imutáveis.
- **Erros onde você os cometeu.** Os argumentos são verificados antes do envio: uma chamada
  errada lança `InvalidArgument` na sua linha de código, e não uma recusa do servidor depois.
- **O bot segue as mesmas regras que uma pessoa.** O bot não tem porta dos fundos: os direitos
  de moderador, os limites e as regras da sala são os mesmos.
- **Seu código não derruba o bot.** Uma exceção em um manipulador, comando ou temporizador não
  para o bot: ela vai para `on_error` e o bot continua funcionando.
- **Assinar só o necessário.** O bot recebe os eventos para os quais você escreveu um
  manipulador, além do chat e da entrada e saída de pessoas.
- **Compatível com o Highrise.** Os nomes dos campos e o formato dos quadros coincidem com o SDK
  oficial do Highrise, então um código conhecido se lê do mesmo jeito.

## Versões e requisitos

| O quê | Valor |
|---|---|
| Python | 3.13 e mais novo |
| Dependências | `aiohttp` |
| Versão do SDK | 0.3.0 |
| Do dono do bot | uma assinatura PREMIUM ativa |
