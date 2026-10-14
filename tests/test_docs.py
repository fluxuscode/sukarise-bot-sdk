"""Документация не должна расходиться с кодом.

Проверяется, что описаны все публичные имена, что у полей моделей есть описания, что
каждое действие бота и каждый обработчик упомянуты в справочниках, что блоки кода в
документации разбираются (а встроенные тесты выполняются) и что ссылки между страницами
ведут туда, куда нужно.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

import sukarisebot
from sukarisebot import Bot, BotAPI, Harness, JsonStore, Room

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PAGES = [ROOT / "README.md", *sorted(DOCS.glob("*.md"))]
SOURCES = sorted((ROOT / "src" / "sukarisebot").glob("*.py"))
FENCE = re.compile(r"^```python\r?\n(.*?)^```", re.S | re.M)
SIGNATURE = re.compile(r"(async )?def \w+\(.*\)( -> [^\n]+)?\s*", re.S)


def public_methods(cls: type) -> list[str]:
    return [
        name
        for name, member in vars(cls).items()
        if not name.startswith("_") and (inspect.isfunction(member) or isinstance(member, property))
    ]


def doc_blocks() -> Iterator[tuple[Path, int, str]]:
    for page in PAGES:
        for index, match in enumerate(FENCE.finditer(page.read_text(encoding="utf-8")), 1):
            yield page, index, match.group(1)


def is_reference_only(code: str) -> bool:
    """A signature, a one-line statement snippet or a deliberately wrong example."""
    snippet = re.search(r"^(\w+ = )?await ", code, re.M) is not None
    return "← ошибка" in code or SIGNATURE.fullmatch(code) is not None or snippet


def slug(heading: str) -> str:
    """The anchor GitHub makes for a heading."""
    text = heading.strip().lower().replace("`", "")
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(page: Path) -> set[str]:
    found: set[str] = set()
    in_code = False
    for line in page.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("#"):
            found.add(slug(line.lstrip("#")))
    return found


# ---- описания в коде ---------------------------------------------------------------


def test_every_exported_class_and_function_has_a_description() -> None:
    missing = [
        name
        for name in sukarisebot.__all__
        if (inspect.isclass(obj := getattr(sukarisebot, name)) or inspect.isfunction(obj)) and not (obj.__doc__ or "").strip()
    ]
    assert not missing, f"без описания: {missing}"


@pytest.mark.parametrize("source", SOURCES, ids=lambda path: path.name)
def test_every_public_constant_and_alias_has_a_description(source: Path) -> None:
    """Под присваиванием, `type X = ...` и т. п. должна стоять строка-описание."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    problems: list[str] = []
    for index, statement in enumerate(tree.body):
        names: list[str] = []
        if isinstance(statement, ast.Assign):
            names = [target.id for target in statement.targets if isinstance(target, ast.Name)]
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            names = [statement.target.id]
        elif isinstance(statement, ast.TypeAlias):
            names = [statement.name.id]
        names = [name for name in names if not name.startswith("_") and name not in {"log"}]
        if not names:
            continue
        following = tree.body[index + 1] if index + 1 < len(tree.body) else None
        described = (
            isinstance(following, ast.Expr)
            and isinstance(following.value, ast.Constant)
            and isinstance(following.value.value, str)
        )
        if not described:
            problems.extend(names)
    assert not problems, f"{source.name}: без описания {problems}"


@pytest.mark.parametrize("cls", [Bot, BotAPI, Room, JsonStore, Harness])
def test_every_public_method_has_a_description(cls: type) -> None:
    undocumented = []
    for name in public_methods(cls):
        member = getattr(cls, name)
        doc = member.fget.__doc__ if isinstance(member, property) else member.__doc__
        if not doc or not doc.strip():
            undocumented.append(name)
    assert not undocumented, f"{cls.__name__}: без описания {undocumented}"


@pytest.mark.parametrize("name", [n for n in dir(BotAPI) if not n.startswith("_")])
def test_every_api_method_lists_its_exceptions(name: str) -> None:
    doc = inspect.getdoc(getattr(BotAPI, name)) or ""
    assert ":raises" in doc or "Исключения — как у" in doc, f"{name}: нет :raises"


@pytest.mark.parametrize("source", SOURCES, ids=lambda path: path.name)
def test_every_dataclass_field_has_an_attribute_description(source: Path) -> None:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name.startswith("_") or not any(
            isinstance(d, ast.Call) and getattr(d.func, "id", "") == "dataclass" for d in node.decorator_list
        ):
            continue
        body = node.body
        for index, statement in enumerate(body):
            if not (isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)):
                continue
            if statement.target.id.startswith("_"):
                continue
            following = body[index + 1] if index + 1 < len(body) else None
            described = (
                isinstance(following, ast.Expr)
                and isinstance(following.value, ast.Constant)
                and isinstance(following.value.value, str)
            )
            if not described:
                problems.append(f"{node.name}.{statement.target.id}")
    assert not problems, f"поля без описания: {problems}"


# ---- справочники упоминают всё -------------------------------------------------------


def page_text(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_the_api_reference_covers_every_action() -> None:
    text = page_text("api.md")
    missing = [name for name in public_methods(BotAPI) if f"`{name}" not in text and f"### `{name}`" not in text]
    assert not missing, f"в docs/api.md нет: {missing}"


def test_the_handler_reference_covers_every_handler() -> None:
    text = page_text("handlers.md")
    handlers = [name for name in public_methods(Bot) if name.startswith("on_")]
    missing = [name for name in handlers if f"### `{name}`" not in text]
    assert not missing, f"в docs/handlers.md нет: {missing}"


def test_the_models_reference_covers_every_model() -> None:
    text = page_text("models.md")
    models = [name for name, member in vars(sukarisebot.models).items() if dataclasses.is_dataclass(member)]
    models += ["Location", "Event", "Facing", "Reaction", "GoldBar", "ModerationAction"]
    missing = [name for name in models if f"`{name}`" not in text]
    assert not missing, f"в docs/models.md нет: {missing}"


def test_the_tools_reference_covers_the_room_and_the_store() -> None:
    text = page_text("tools.md")
    for name in public_methods(Room) + public_methods(JsonStore):
        assert name in text, f"в docs/tools.md нет: {name}"


# ---- блоки кода и ссылки --------------------------------------------------------------


def test_every_python_block_in_the_docs_parses() -> None:
    broken = []
    for page, index, code in doc_blocks():
        if is_reference_only(code):
            continue
        try:
            ast.parse(code)
        except SyntaxError as error:
            broken.append(f"{page.name} блок {index}: {error.msg} (строка {error.lineno})")
    assert not broken, broken


def test_the_tests_shown_in_the_docs_pass() -> None:
    ran = 0
    for page, index, code in doc_blocks():
        if "def test_" not in code:
            continue
        namespace: dict[str, object] = {"__name__": f"doc_{page.stem}_{index}"}
        exec(compile(code, f"{page.name}#{index}", "exec"), namespace)
        for name, function in list(namespace.items()):
            if name.startswith("test_") and callable(function):
                function()
                ran += 1
    assert ran >= 6, "в документации должны быть примеры тестов"


def test_links_between_pages_resolve() -> None:
    link = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
    problems: list[str] = []
    for page in PAGES:
        text = page.read_text(encoding="utf-8")
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        text = re.sub(r"`[^`\n]*`", "", text)  # ссылки внутри кода — не ссылки
        for match in link.finditer(text):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, anchor = target.partition("#")
            destination = page if not path_part else (page.parent / path_part).resolve()
            if not destination.exists():
                problems.append(f"{page.name}: нет файла {target}")
                continue
            if anchor and destination.suffix == ".md" and anchor not in anchors(destination):
                problems.append(f"{page.name}: нет якоря #{anchor} в {destination.name}")
    assert not problems, problems


def test_the_examples_are_listed_in_the_readme() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "examples/" in readme
    for example in sorted((ROOT / "examples").glob("*.py")):
        assert example.read_text(encoding="utf-8").lstrip().startswith('"""'), f"{example.name}: нет описания"
