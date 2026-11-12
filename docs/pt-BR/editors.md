[English](../en/editors.md) | [Русский](../ru/editors.md) | **Português (Brasil)**

# Editores e dicas

O SDK foi escrito para que o editor ajude a cada passo: sugere métodos e seus argumentos, mostra
a descrição ao passar o mouse e pega erros de digitação em valores e tipos errados antes de você
executar qualquer coisa. Esta página explica o que foi feito para isso e como ativar as dicas no
**PyCharm**, no **VS Code** e em outros editores.

## O que o SDK dá ao editor

| O quê | Como ajuda |
|---|---|
| **Tipos em todo lugar** | Todas as funções, métodos e atributos públicos têm anotações de tipo. O editor sugere os argumentos e o resultado (`await self.api.gold()` é um `int`). |
| **O marcador `py.typed`** | O pacote é marcado como tipado (PEP 561). Os verificadores de tipos (mypy, pyright, PyCharm) usam as anotações dele em vez de tratar o pacote como uma "caixa-preta". |
| **Descrições no código** | Toda classe, método, função e campo de modelo tem uma descrição (escrita em russo). Ela aparece ao passar o mouse e na janela de documentação rápida. |
| **O formato das descrições** | As descrições usam campos do reStructuredText: `:param nome:`, `:returns:`, `:raises Exceção:`. O PyCharm (formato padrão) e o Pylance os entendem. |
| **Literais** | `Reaction`, `GoldBar`, `Facing`, `ModerationAction` são listas de strings permitidas. O editor as oferece ao digitar e o verificador pega um erro de digitação. |
| **Descrições dos campos dos modelos** | Os campos de `User`, `Position`, `ChatEvent` e dos demais têm descrição: passe o mouse sobre `user.username`. |
| **`__all__`** | O pacote lista explicitamente o que exporta, então o autocompletar de `from sukarisebot import …` mostra só o necessário. |
| **Verificação estrita** | O próprio SDK passa no `mypy --strict` e no `pyright` no modo `strict`: os tipos não "vazam" para o seu código como `Any`. |

## PyCharm

1. **Interpretador.** É preciso Python 3.13 ou mais novo. Abra **Settings → Project → Python
   Interpreter** e confirme que está selecionado o ambiente em que o SDK está instalado
   (`pip install -e .`). Se o PyCharm sublinha `import sukarisebot` como não resolvido, o
   interpretador selecionado é o errado.
2. **Versão do PyCharm.** O SDK usa a sintaxe do Python 3.12 ou mais nova: a instrução
   `type X = …` e parâmetros de tipo em funções (`async def wait_for[E: Event](…)`). As versões
   modernas do PyCharm (**2024.1 e mais novas**) a entendem. Em versões muito antigas esses
   trechos podem aparecer destacados como erros, embora o código funcione.
3. **Dicas ao digitar.**
   - Comece a digitar `self.api.` e o PyCharm mostra todas as ações do bot.
   - **Quick Documentation**: a descrição de um método ou campo: `Ctrl+Q` (Windows e Linux),
     `F1` (macOS) ou apenas deixe o cursor parado sobre ele.
   - **Parameter Info**: os parâmetros da chamada: `Ctrl+P` dentro dos parênteses.
   - **Go to Declaration**: ir para a definição: `Ctrl+B`.
4. **Sobrescrever manipuladores.** Para não digitar à mão a assinatura de um manipulador,
   pressione **Code → Override Methods…** (`Ctrl+O`) no corpo da classe do bot, escolha
   `on_chat`, `on_user_join` e outros, e o PyCharm gera um método com a assinatura e os tipos
   corretos.
5. **O formato das descrições.** As descrições do SDK usam o estilo reStructuredText, que no
   PyCharm vem ativado por padrão (**Settings → Tools → Python Integrated Tools → Docstrings →
   Docstring format → reStructuredText**). Se você trocou o formato, volte a ele para que
   `:param:`, `:returns:` e `:raises:` apareçam bem.
6. **Verificação de tipos.** As inspeções embutidas do PyCharm encontram muitos erros na hora.
   Para a verificação estrita completa, adicione uma ferramenta externa: o plugin **Mypy** ou a
   execução de `mypy` no terminal (veja abaixo).
7. **Trabalhando a partir de um repositório clonado.** Se você estiver editando o próprio SDK,
   marque o diretório `src` como **Sources Root** (clique direito → *Mark Directory as → Sources
   Root*).

## Visual Studio Code

1. Instale a extensão **Python** (ela traz o **Pylance**) e selecione um interpretador Python
   3.13 (`Ctrl+Shift+P` → *Python: Select Interpreter*) que tenha o SDK instalado.
2. As dicas funcionam de imediato: passe o mouse sobre um método para ver a descrição;
   `Ctrl+Shift+Space` dentro dos parênteses mostra os parâmetros.
3. Para receber avisos de tipos, ative a verificação nas configurações (`settings.json`):

   ```json
   {
     "python.analysis.typeCheckingMode": "strict"
   }
   ```

   Por padrão o Pylance quase não mostra avisos de tipos (`off`); `basic` é um começo razoável,
   `strict` é o modo mais rigoroso, como o do próprio SDK. (Se o diretório tiver um
   `pyproject.toml` com uma seção `[tool.pyright]`, as configurações são tiradas de lá.)

## Outros editores

Neovim, Helix, Sublime Text, Emacs, Zed e outros conversam com servidores de linguagem pelo
protocolo LSP. Basta conectar um servidor que entenda os tipos do Python:

- **pyright** ou **basedpyright**: o mesmo motor do Pylance;
- **pylsp** com o plugin `pylsp-mypy`: baseado no mypy;
- **jedi-language-server**: dicas sem verificação estrita de tipos.

O SDK funciona com todos: as descrições são lidas do código-fonte, e os tipos, das anotações e
do arquivo `py.typed`.

## Verificação de tipos pela linha de comando

As duas verificações já estão configuradas no `pyproject.toml` do SDK. Execute-as a partir da
raiz do repositório:

```bash
python -m mypy          # strict mode, see [tool.mypy]
python -m pyright       # strict mode, see [tool.pyright]
```

Você pode verificar o código do **seu próprio bot** com as mesmas regras estritas acrescentando
ao `pyproject.toml` dele:

```toml
[tool.mypy]
strict = true

[tool.pyright]
typeCheckingMode = "strict"
```

## O que os tipos sugerem: exemplos

```python
from sukarisebot import Bot, Position, User


class Demo(Bot):
    async def on_chat(self, user: User, message: str) -> None:
        await self.api.react("hart", user.id)          # ← error: allowed are clap, heart, thumbs, wave, wink
        await self.api.move_to(Position(1.0, 0.0))     # ← error: the argument z is missing
        gold: str = await self.api.gold()              # ← error: gold() returns an int
```

Um verificador de tipos encontra esses erros antes da execução. Se você mesmo assim executasse o
código, o SDK os pegaria em tempo de execução: um `InvalidArgument` com um texto claro.

### Dica: `match` em eventos e posições

`Location` e `Event` são uniões. Desmonte-as com `match`; o verificador confirmará que você
cobriu todas as variantes:

```python
from sukarisebot import AnchorPosition, Location, Position


def describe(location: Location) -> str:
    match location:
        case Position(x=x, z=z):
            return f"on the floor ({x:.1f}, {z:.1f})"
        case AnchorPosition(entity_id=furniture):
            return f"on the furniture {furniture}"
```

### Dica: dados em `state` e `user_state`

`self.state` e `self.user_state(id)` são dicionários `dict[str, object]`, então os valores têm
tipo `object`. Antes de usar um valor, estreite o tipo com uma verificação:

```python
from sukarisebot import Bot


class Counter(Bot):
    def bump(self) -> int:
        value = self.state.get("count", 0)
        count = (value if isinstance(value, int) else 0) + 1
        self.state["count"] = count
        return count
```

## Se não há dicas

| Sintoma | Causa possível e solução |
|---|---|
| `import sukarisebot` está sublinhado como não resolvido | O editor usa um interpretador diferente daquele em que o SDK está instalado. Selecione o certo ou execute `pip install -e .` no ambiente atual. |
| O autocompletar não mostra os métodos de `self.api.` | O editor não inferiu o tipo de `self.api`. Confirme que a classe herda `Bot` e que o interpretador está selecionado corretamente. |
| As descrições não aparecem | Instale o SDK como pacote (`pip install -e .`), e não copiando arquivos, para que o `py.typed` fique ao lado. No PyCharm verifique o formato das descrições (reStructuredText). |
| Erros destacados em `type X = …` e `def f[T]()` | O editor é mais antigo que a sintaxe do Python 3.12. Atualize o editor. |
| `reportPrivateUsage` ou parecido no seu bot | Não mexa em membros com sublinhado (`bot._engine` e assim por diante): são detalhes internos que podem mudar. |
