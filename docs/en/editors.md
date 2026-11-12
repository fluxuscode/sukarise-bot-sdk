**English** | [Русский](../ru/editors.md) | [Português (Brasil)](../pt-BR/editors.md)

# Editors and hints

The SDK is written so that your editor helps at every step: it suggests methods and their
arguments, shows a description on hover, and catches typos in values and wrong types before you
run anything. This page explains what has been done for that and how to turn the hints on in
**PyCharm**, **VS Code** and other editors.

## What the SDK gives the editor

| What | How it helps |
|---|---|
| **Types everywhere** | All public functions, methods and attributes have type annotations. The editor suggests arguments and the result (`await self.api.gold()` is an `int`). |
| **The `py.typed` marker** | The package is marked as typed (PEP 561). Type checkers (mypy, pyright, PyCharm) use its annotations instead of treating the package as a "black box". |
| **Descriptions in the code** | Every class, method, function and model field has a description (written in Russian). It is shown on hover and in the quick documentation window. |
| **The description format** | The descriptions are written with reStructuredText fields: `:param name:`, `:returns:`, `:raises Exception:`. PyCharm (its default format) and Pylance understand them. |
| **Literals** | `Reaction`, `GoldBar`, `Facing`, `ModerationAction` are lists of allowed strings. The editor offers them as you type and a checker catches a typo. |
| **Descriptions of model fields** | The fields of `User`, `Position`, `ChatEvent` and the rest have a description: hover over `user.username`. |
| **`__all__`** | The package lists explicitly what it exports, so the autocompletion of `from sukarisebot import …` shows only what is needed. |
| **Strict checking** | The SDK itself passes `mypy --strict` and `pyright` in `strict` mode: types do not "leak" into your code as `Any`. |

## PyCharm

1. **Interpreter.** Python 3.13 or newer is needed. Open **Settings → Project → Python
   Interpreter** and make sure the environment the SDK is installed into is selected
   (`pip install -e .`). If PyCharm underlines `import sukarisebot` as unresolved, the wrong
   interpreter is selected.
2. **PyCharm version.** The SDK uses Python 3.12+ syntax: the `type X = …` statement and type
   parameters in functions (`async def wait_for[E: Event](…)`). Modern versions of PyCharm
   (**2024.1 and newer**) understand it. In very old versions such places may be highlighted as
   errors even though the code works.
3. **Hints as you type.**
   - Start typing `self.api.` and PyCharm shows all the bot's actions.
   - **Quick Documentation**: the description of a method or field: `Ctrl+Q` (Windows and
     Linux), `F1` (macOS) or just hold the cursor over it.
   - **Parameter Info**: the call's parameters: `Ctrl+P` inside the brackets.
   - **Go to Declaration**: jump to the definition: `Ctrl+B`.
4. **Overriding handlers.** To avoid typing a handler's signature by hand, press **Code →
   Override Methods…** (`Ctrl+O`) in the body of the bot's class, choose `on_chat`,
   `on_user_join` and others, and PyCharm generates a method with the right signature and types.
5. **The description format.** The SDK's descriptions are written in the reStructuredText style,
   which is on by default in PyCharm (**Settings → Tools → Python Integrated Tools → Docstrings →
   Docstring format → reStructuredText**). If you switched the format, switch it back so that
   `:param:`, `:returns:` and `:raises:` display nicely.
6. **Type checking.** PyCharm's built-in inspections find many errors at once. For full strict
   checking add an external tool: the **Mypy** plugin or running `mypy` from the terminal (see
   below).
7. **Working from a cloned repository.** If you are editing the SDK itself, mark the `src`
   directory as a **Sources Root** (right click → *Mark Directory as → Sources Root*).

## Visual Studio Code

1. Install the **Python** extension (it pulls in **Pylance**) and select a Python 3.13 interpreter
   (`Ctrl+Shift+P` → *Python: Select Interpreter*) that has the SDK installed.
2. Hints work out of the box: hover over a method to see its description; `Ctrl+Shift+Space`
   inside the brackets shows the parameters.
3. To get type warnings, turn the checking on in the settings (`settings.json`):

   ```json
   {
     "python.analysis.typeCheckingMode": "strict"
   }
   ```

   By default Pylance shows almost no type warnings (`off`); `basic` is a reasonable start,
   `strict` is the strictest mode, like the SDK's own. (If the directory has a `pyproject.toml`
   with a `[tool.pyright]` section, the settings are taken from there.)

## Other editors

Neovim, Helix, Sublime Text, Emacs, Zed and others talk to language servers over the LSP
protocol. It is enough to connect a server that understands Python types:

- **pyright** or **basedpyright**: the same engine as in Pylance;
- **pylsp** with the `pylsp-mypy` plugin: based on mypy;
- **jedi-language-server**: hints without strict type checking.

The SDK works with all of them: descriptions are read from the source code, and types from the
annotations and the `py.typed` file.

## Type checking from the command line

Both checks are already set up in the SDK's `pyproject.toml`. Run them from the repository's root:

```bash
python -m mypy          # strict mode, see [tool.mypy]
python -m pyright       # strict mode, see [tool.pyright]
```

You can check **your own bot's** code with the same strict rules by adding to its
`pyproject.toml`:

```toml
[tool.mypy]
strict = true

[tool.pyright]
typeCheckingMode = "strict"
```

## What types suggest: examples

```python
from sukarisebot import Bot, Position, User


class Demo(Bot):
    async def on_chat(self, user: User, message: str) -> None:
        await self.api.react("hart", user.id)          # ← error: allowed are clap, heart, thumbs, wave, wink
        await self.api.move_to(Position(1.0, 0.0))     # ← error: the argument z is missing
        gold: str = await self.api.gold()              # ← error: gold() returns an int
```

A type checker finds these errors before running. If you did run the code, the SDK would catch
them at run time: an `InvalidArgument` with a clear text.

### Tip: `match` on events and positions

`Location` and `Event` are unions. Take them apart with `match`; a checker will verify that you
covered all the variants:

```python
from sukarisebot import AnchorPosition, Location, Position


def describe(location: Location) -> str:
    match location:
        case Position(x=x, z=z):
            return f"on the floor ({x:.1f}, {z:.1f})"
        case AnchorPosition(entity_id=furniture):
            return f"on the furniture {furniture}"
```

### Tip: data in `state` and `user_state`

`self.state` and `self.user_state(id)` are `dict[str, object]` dictionaries, so the values have
type `object`. Before using a value, narrow its type with a check:

```python
from sukarisebot import Bot


class Counter(Bot):
    def bump(self) -> int:
        value = self.state.get("count", 0)
        count = (value if isinstance(value, int) else 0) + 1
        self.state["count"] = count
        return count
```

## If there are no hints

| Symptom | Possible cause and solution |
|---|---|
| `import sukarisebot` is underlined as unresolved | The editor uses a different interpreter from the one the SDK is installed into. Select the right one or run `pip install -e .` in the current environment. |
| Autocompletion does not show the `self.api.` methods | The editor did not infer the type of `self.api`. Make sure the class inherits `Bot` and that the interpreter is selected correctly. |
| Descriptions are not displayed | Install the SDK as a package (`pip install -e .`), not by copying files, so that `py.typed` is next to it. In PyCharm check the description format (reStructuredText). |
| Errors highlighted on `type X = …` and `def f[T]()` | The editor is older than the Python 3.12 syntax. Update the editor. |
| `reportPrivateUsage` or similar in your bot | Do not touch members with an underscore (`bot._engine` and so on): they are internals that may change. |
