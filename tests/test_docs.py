"""The documentation must not drift away from the code, nor the languages from each other.

Three languages are kept: English (``README.md``, ``docs/en``), Russian (``README.ru.md``,
``docs/ru``) and Brazilian Portuguese (``README.pt-BR.md``, ``docs/pt-BR``). The tests check that

* every public name is described in the code, and every action, handler, model and tool is
  listed in the reference pages of every language;
* the Python blocks in the documentation parse, and the tests shown in it pass;
* links between pages (and their anchors) resolve;
* the three languages have the same pages, the same headings, tables and links, the same code
  blocks (byte for byte, mermaid diagrams aside: their labels are prose), and a language
  switcher on top; and none of the pages was left untranslated.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

import sukarisebot
from sukarisebot import Bot, BotAPI, Harness, JsonStore, Room

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LANGS = ("en", "ru", "pt-BR")
SUFFIX = {"en": "", "ru": ".ru", "pt-BR": ".pt-BR"}
NAME = {"en": "English", "ru": "Русский", "pt-BR": "Português (Brasil)"}
SOURCES = sorted((ROOT / "src" / "sukarisebot").glob("*.py"))
FENCE = re.compile(r"^```(\w*)\r?\n(.*?)^```", re.S | re.M)
SIGNATURE = re.compile(r"(async )?def \w+\(.*\)( -> [^\n]+)?\s*", re.S)
CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def root_page(stem: str, lang: str) -> Path:
    return ROOT / f"{stem}{SUFFIX[lang]}.md"


def pages(lang: str) -> list[Path]:
    return [root_page("README", lang), root_page("CHANGELOG", lang), *sorted((DOCS / lang).glob("*.md"))]


ALL_PAGES = [page for lang in LANGS for page in pages(lang)]


def read(page: Path) -> str:
    return page.read_text(encoding="utf-8").replace("\r\n", "\n")


def public_methods(cls: type) -> list[str]:
    return [
        name
        for name, member in vars(cls).items()
        if not name.startswith("_") and (inspect.isfunction(member) or isinstance(member, property))
    ]


def doc_blocks(lang: str | None = None) -> Iterator[tuple[Path, int, str]]:
    for page in ALL_PAGES if lang is None else pages(lang):
        for index, match in enumerate(FENCE.finditer(read(page)), 1):
            if match.group(1) == "python":
                yield page, index, match.group(2)


def is_reference_only(code: str) -> bool:
    """A signature, a one-line statement snippet or a deliberately wrong example."""
    snippet = re.search(r"^(\w+ = )?await ", code, re.M) is not None
    return "← error" in code or SIGNATURE.fullmatch(code) is not None or snippet


def slug(heading: str) -> str:
    """The anchor GitHub makes for a heading."""
    text = heading.strip().lower().replace("`", "")
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(page: Path) -> set[str]:
    found: set[str] = set()
    in_code = False
    for line in read(page).splitlines():
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code and line.startswith("#"):
            found.add(slug(line.lstrip("#")))
    return found


# ---- descriptions in the code ------------------------------------------------------------------


def test_every_exported_class_and_function_has_a_description() -> None:
    missing = [
        name
        for name in sukarisebot.__all__
        if (inspect.isclass(obj := getattr(sukarisebot, name)) or inspect.isfunction(obj)) and not (obj.__doc__ or "").strip()
    ]
    assert not missing, f"no description: {missing}"


@pytest.mark.parametrize("source", SOURCES, ids=lambda path: path.name)
def test_every_public_constant_and_alias_has_a_description(source: Path) -> None:
    """A string literal must stand under an assignment, a ``type X = ...`` and the like."""
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
    assert not problems, f"{source.name}: no description for {problems}"


@pytest.mark.parametrize("cls", [Bot, BotAPI, Room, JsonStore, Harness])
def test_every_public_method_has_a_description(cls: type) -> None:
    undocumented = []
    for name in public_methods(cls):
        member = getattr(cls, name)
        doc = member.fget.__doc__ if isinstance(member, property) else member.__doc__
        if not doc or not doc.strip():
            undocumented.append(name)
    assert not undocumented, f"{cls.__name__}: no description for {undocumented}"


@pytest.mark.parametrize("name", [n for n in dir(BotAPI) if not n.startswith("_")])
def test_every_api_method_lists_its_exceptions(name: str) -> None:
    doc = inspect.getdoc(getattr(BotAPI, name)) or ""
    assert ":raises" in doc or "Исключения — как у" in doc, f"{name}: no :raises"


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
    assert not problems, f"fields without a description: {problems}"


# ---- the reference pages mention everything, in every language ------------------------------------


def page_text(lang: str, name: str) -> str:
    return read(DOCS / lang / name)


@pytest.mark.parametrize("lang", LANGS)
def test_the_api_reference_covers_every_action(lang: str) -> None:
    text = page_text(lang, "api.md")
    missing = [name for name in public_methods(BotAPI) if f"`{name}" not in text and f"### `{name}`" not in text]
    assert not missing, f"docs/{lang}/api.md lacks: {missing}"


@pytest.mark.parametrize("lang", LANGS)
def test_the_handler_reference_covers_every_handler(lang: str) -> None:
    text = page_text(lang, "handlers.md")
    handlers = [name for name in public_methods(Bot) if name.startswith("on_")]
    missing = [name for name in handlers if f"### `{name}`" not in text]
    assert not missing, f"docs/{lang}/handlers.md lacks: {missing}"


@pytest.mark.parametrize("lang", LANGS)
def test_the_models_reference_covers_every_model(lang: str) -> None:
    text = page_text(lang, "models.md")
    models = [name for name, member in vars(sukarisebot.models).items() if dataclasses.is_dataclass(member)]
    models += ["Location", "Event", "Facing", "Reaction", "GoldBar", "ModerationAction"]
    missing = [name for name in models if f"`{name}`" not in text]
    assert not missing, f"docs/{lang}/models.md lacks: {missing}"


@pytest.mark.parametrize("lang", LANGS)
def test_the_tools_reference_covers_the_room_and_the_store(lang: str) -> None:
    text = page_text(lang, "tools.md")
    for name in public_methods(Room) + public_methods(JsonStore):
        assert name in text, f"docs/{lang}/tools.md lacks: {name}"


@pytest.mark.parametrize("lang", LANGS)
def test_the_errors_page_lists_every_exception(lang: str) -> None:
    text = page_text(lang, "errors.md")
    names = [n for n in sukarisebot.__all__ if inspect.isclass(c := getattr(sukarisebot, n)) and issubclass(c, sukarisebot.SukaRiseError)]
    assert "RateLimited" in names
    missing = [name for name in names if f"`{name}`" not in text]
    assert not missing, f"docs/{lang}/errors.md lacks: {missing}"


# ---- code blocks and links ---------------------------------------------------------------------------


def test_every_python_block_in_the_docs_parses() -> None:
    broken = []
    for page, index, code in doc_blocks():
        if is_reference_only(code):
            continue
        try:
            ast.parse(code)
        except SyntaxError as error:
            broken.append(f"{page.name} block {index}: {error.msg} (line {error.lineno})")
    assert not broken, broken


@pytest.mark.parametrize("lang", LANGS)
def test_the_tests_shown_in_the_docs_pass(lang: str) -> None:
    ran = 0
    for page, index, code in doc_blocks(lang):
        if "def test_" not in code:
            continue
        namespace: dict[str, object] = {"__name__": f"doc_{page.stem}_{index}"}
        exec(compile(code, f"{page.name}#{index}", "exec"), namespace)
        for name, function in list(namespace.items()):
            if name.startswith("test_") and callable(function):
                function()
                ran += 1
    assert ran >= 6, "the documentation must show example tests"


@pytest.mark.parametrize("page", ALL_PAGES, ids=lambda page: str(page.relative_to(ROOT)))
def test_links_between_pages_resolve(page: Path) -> None:
    link = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
    text = re.sub(r"```.*?```", "", read(page), flags=re.S)
    text = re.sub(r"`[^`\n]*`", "", text)  # a link inside code is not a link
    problems: list[str] = []
    for match in link.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path_part, _, anchor = target.partition("#")
        destination = page if not path_part else (page.parent / path_part).resolve()
        if not destination.exists():
            problems.append(f"no file {target}")
            continue
        if anchor and destination.suffix == ".md" and anchor not in anchors(destination):
            problems.append(f"no anchor #{anchor} in {destination.name}")
    assert not problems, problems


def test_the_examples_are_listed_in_the_readme() -> None:
    readme = read(ROOT / "README.md")
    assert "examples/" in readme
    for example in sorted((ROOT / "examples").glob("*.py")):
        assert example.read_text(encoding="utf-8").lstrip().startswith('"""'), f"{example.name}: no description"


# ---- the three languages say the same -----------------------------------------------------------------


def structure(text: str) -> dict[str, object]:
    """What must be equal in every language: the shape of a page, not its words."""
    body = FENCE.sub("", text)
    headings = [len(match.group(1)) for match in re.finditer(r"^(#{1,6}) ", body, re.M)]
    tables: list[tuple[int, int]] = []
    rows: list[str] = []
    for line in [*body.splitlines(), ""]:
        if line.startswith("|"):
            rows.append(line)
        elif rows:
            tables.append((rows[0].count("|"), len(rows)))
            rows = []
    links: list[str] = []
    prose = re.sub(r"`[^`\n]*`", "", body)
    for match in re.finditer(r"\[[^\]]*\]\(([^)\s]+)\)", prose):
        target = match.group(1).partition("#")[0]
        if target.startswith(("http://", "https://")):
            # a site may have a page per language (keepachangelog.com/en, /ru, /pt-BR): compare the host
            links.append(target.split("/")[2])
            continue
        target = re.sub(r"(docs/|\.\./|^)(en|ru|pt-BR)/", r"\1<lang>/", target)
        target = re.sub(r"(^|/)(README|CHANGELOG)\.(ru|pt-BR)\.md$", r"\1\2.md", target)
        links.append(target)
    blocks = [(m.group(1), m.group(2)) for m in FENCE.finditer(text)]
    return {"headings": headings, "tables": tables, "links": links, "blocks": blocks, "bullets": text.count("\n- ")}


def counterpart(page: Path, lang: str) -> Path:
    if page.parent == ROOT:
        return root_page(page.name.split(".")[0], lang)
    return DOCS / lang / page.name


def test_the_three_languages_have_the_same_pages() -> None:
    names = {lang: {page.name for page in (DOCS / lang).glob("*.md")} for lang in LANGS}
    assert names["en"] == names["ru"] == names["pt-BR"], {lang: sorted(n) for lang, n in names.items()}
    assert len(names["en"]) >= 14
    for lang in LANGS:
        for stem in ("README", "CHANGELOG"):
            assert root_page(stem, lang).exists()


@pytest.mark.parametrize("page", pages("en"), ids=lambda page: str(page.relative_to(ROOT)))
@pytest.mark.parametrize("lang", ["ru", "pt-BR"])
def test_a_translation_has_the_structure_of_the_english_page(page: Path, lang: str) -> None:
    other = counterpart(page, lang)
    assert other.exists(), f"{other.relative_to(ROOT)} is missing"
    english, translated = structure(read(page)), structure(read(other))
    for key in ("headings", "tables", "links", "bullets"):
        assert translated[key] == english[key], f"{other.relative_to(ROOT)}: {key} differ from {page.relative_to(ROOT)}"
    english_blocks, translated_blocks = english["blocks"], translated["blocks"]
    assert isinstance(english_blocks, list) and isinstance(translated_blocks, list)
    assert [tag for tag, _ in translated_blocks] == [tag for tag, _ in english_blocks], f"{other.name}: block kinds differ"
    for (tag, left), (_, right) in zip(english_blocks, translated_blocks, strict=True):
        if tag != "mermaid":  # the labels of a diagram are prose and are translated
            assert left == right, f"{other.relative_to(ROOT)}: a {tag} block differs from the English page:\n{right}"


# Placeholders that are words of the language, not identifiers: each language writes its own.
LOCALIZED_PLACEHOLDERS = frozenset(
    ("pip install file-name.whl", "(calls, seconds)", ":param name:", ":raises Exception:", "change(old)")
)


def test_inline_code_is_not_lost_in_translation() -> None:
    """The identifiers, numbers and values in backticks are the facts: every language keeps them."""
    technical = re.compile(r"^[\w.:()=\-/#<>,\[\]\"'{}*|+@ ]+$")
    problems: list[str] = []
    for page in pages("en"):
        for lang in ("ru", "pt-BR"):
            other = counterpart(page, lang)
            spans = Counter(s for s in re.findall(r"`([^`\n]+)`", FENCE.sub("", read(page))) if technical.match(s) and s.isascii())
            kept = Counter(s for s in re.findall(r"`([^`\n]+)`", FENCE.sub("", read(other))) if technical.match(s) and s.isascii())
            lost = {span: count for span, count in (spans - kept).items() if span not in LOCALIZED_PLACEHOLDERS}
            if lost:
                problems.append(f"{other.relative_to(ROOT)} lacks {lost}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("lang", LANGS)
def test_every_page_starts_with_the_language_switcher(lang: str) -> None:
    for page in pages(lang):
        first = read(page).splitlines()[0]
        parts = [part.strip() for part in first.split("|")]
        assert len(parts) == 3, f"{page.relative_to(ROOT)}: the first line is not a switcher"
        for part, other in zip(parts, LANGS, strict=True):
            if other == lang:
                assert part == f"**{NAME[other]}**", f"{page.relative_to(ROOT)}: {part!r}"
            else:
                target = counterpart(page, other)
                relative = target.relative_to(page.parent) if target.parent == page.parent else Path("../") / target.relative_to(DOCS)
                if page.parent == ROOT:
                    relative = target.relative_to(ROOT)
                assert part == f"[{NAME[other]}]({relative.as_posix()})", f"{page.relative_to(ROOT)}: {part!r}"


@pytest.mark.parametrize("lang", ["en", "pt-BR"])
def test_a_page_outside_russian_has_no_cyrillic_prose(lang: str) -> None:
    offenders = []
    for page in pages(lang):
        # The name of the language in its own language is allowed ("Русский" in the switcher and links).
        lines = [line.replace("Русский", "") for line in read(page).splitlines()]
        if any(CYRILLIC.search(line) for line in lines):
            offenders.append(page.relative_to(ROOT).as_posix())
    assert not offenders, f"Russian text left in: {offenders}"


def test_russian_pages_are_russian() -> None:
    for page in pages("ru"):
        assert len(CYRILLIC.findall(read(page))) > 100, f"{page.name} does not look Russian"


def test_the_portuguese_pages_are_portuguese_not_english_copies() -> None:
    for page in pages("pt-BR"):
        text = re.sub(r"`[^`\n]*`", "", FENCE.sub("", read(page)))  # code and the server's English texts do not count
        if len(text) < 1500:
            continue
        words = re.findall(r"[a-zà-ú]+", text.lower())
        portuguese = sum(words.count(word) for word in ("que", "para", "não", "uma", "com", "ou", "do", "da", "os", "as"))
        english = sum(words.count(word) for word in ("the", "and", "with", "that", "is", "are", "of"))
        assert portuguese > 3 * english, f"{page.relative_to(ROOT)} looks untranslated ({portuguese} pt words, {english} en)"
        assert text != FENCE.sub("", read(counterpart(page, "en")))


def test_the_english_pages_are_english() -> None:
    for page in pages("en"):
        text = FENCE.sub("", read(page))
        if len(text) < 1500:
            continue
        words = re.findall(r"[a-z]+", text.lower())
        assert sum(words.count(word) for word in ("the", "and", "of", "is", "to")) > 20, f"{page.name} does not look English"


def test_the_docs_paths_mentioned_in_the_source_exist() -> None:
    """Docstrings and examples point at pages by path; moving the docs must not leave dead ones."""
    mention = re.compile(r"docs/[\w./-]+\.md")
    missing = []
    for source in [*SOURCES, *sorted((ROOT / "examples").glob("*.py"))]:
        for path in mention.findall(source.read_text(encoding="utf-8")):
            if not (ROOT / path).exists():
                missing.append(f"{source.name}: {path}")
    assert not missing, missing
