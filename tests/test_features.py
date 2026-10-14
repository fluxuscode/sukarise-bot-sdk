"""Storage, outfit rules, the command line, the HTTP client and my_outfit."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from sukarisebot import Bot, InvalidArgument, Item, JsonStore, category_of, load_bot, outfit_problems
from sukarisebot.cli import main
from sukarisebot.testing import Harness


def run(coro: object) -> None:
    asyncio.run(coro)  # type: ignore[arg-type]


# ---- JsonStore ----------------------------------------------------------------


def test_values_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "data.json"

    async def first_run() -> None:
        store = JsonStore(path)
        await store.set("user-1", {"username": "alice", "visits": 2})
        await store.update("total", lambda old: (old if isinstance(old, int) else 0) + 5)

    async def second_run() -> None:
        store = JsonStore(path)
        assert await store.get("user-1") == {"username": "alice", "visits": 2}
        assert await store.get("total") == 5
        assert await store.get("missing", "fallback") == "fallback"

    run(first_run())
    run(second_run())
    assert json.loads(path.read_text(encoding="utf-8"))["total"] == 5


def test_concurrent_updates_are_not_lost(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = JsonStore(tmp_path / "counter.json")

        async def bump() -> None:
            await store.update("n", lambda old: (old if isinstance(old, int) else 0) + 1)

        await asyncio.gather(*(bump() for _ in range(50)))
        assert await store.get("n") == 50

    run(scenario())


def test_a_write_leaves_no_temporary_files(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = JsonStore(tmp_path / "data.json")
        for index in range(3):
            await store.set("round", index)

    run(scenario())
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["data.json"]


def test_a_file_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    async def scenario() -> None:
        with pytest.raises(ValueError, match="JSON-объект"):
            await JsonStore(path).get("anything")

    run(scenario())


def test_an_empty_file_is_an_empty_store(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text("", encoding="utf-8")

    async def scenario() -> None:
        assert await JsonStore(path).get("anything", 7) == 7

    run(scenario())


# ---- outfit rules --------------------------------------------------------------

BASE = [
    Item(type="clothing", amount=1, id="body-flesh-n_1"),
    Item(type="clothing", amount=1, id="eye-n_1"),
    Item(type="clothing", amount=1, id="eyebrow-n_1"),
    Item(type="clothing", amount=1, id="nose-n_1"),
    Item(type="clothing", amount=1, id="mouth-n_1"),
]


def test_categories_are_read_from_item_ids() -> None:
    assert category_of("shirt-n_room32019denimjacket") == "shirt"
    assert category_of("eyebrow-n_1") == "eyebrow"
    assert category_of("body-flesh-n_1") == "body-flesh"
    assert category_of("hat-n_1") is None


def test_a_complete_outfit_has_no_problems() -> None:
    assert outfit_problems([*BASE, Item(type="clothing", amount=1, id="shirt-n_a"), Item(type="clothing", amount=1, id="pants-n_a")]) == []
    assert outfit_problems([*BASE, Item(type="clothing", amount=1, id="dress-n_a"), Item(type="clothing", amount=1, id="hat-n_a")]) == []


def test_missing_parts_and_uncovered_bodies_are_named() -> None:
    problems = outfit_problems([Item(type="clothing", amount=1, id="eye-n_1")])
    assert "не хватает части тела: mouth" in problems
    assert any("тело не закрыто" in problem for problem in problems)


def test_two_items_of_one_category_are_refused() -> None:
    problems = outfit_problems([*BASE, Item(type="clothing", amount=1, id="mouth-n_2")])
    assert any("два предмета категории mouth" in problem for problem in problems)


def test_the_same_item_twice_is_refused() -> None:
    problems = outfit_problems([*BASE, Item(type="clothing", amount=1, id="hat-n_x"), Item(type="clothing", amount=1, id="hat-n_x")])
    assert any("hat-n_x указан несколько раз (2)" in problem for problem in problems)


def test_wear_checks_the_outfit_before_sending_anything() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()
        with pytest.raises(InvalidArgument, match="не хватает"):
            await harness.bot.api.wear([Item(type="clothing", amount=1, id="eye-n_1")])
        assert harness.requests("SetOutfitRequest") == []
        complete = [*BASE, Item(type="clothing", amount=1, id="dress-n_1")]
        await harness.bot.api.wear(complete)
        assert len(harness.requests("SetOutfitRequest")) == 1

    run(scenario())


def test_my_outfit_asks_the_server_for_the_bots_own_outfit() -> None:
    async def scenario() -> None:
        harness = Harness(Bot(), bot_id="bot-42")
        await harness.start()
        assert await harness.bot.my_outfit() == []
        (sent,) = harness.requests("GetUserOutfitRequest")
        assert sent.body == {"user_id": "bot-42"}

    run(scenario())


# ---- HTTP client and command line -----------------------------------------------


def test_the_shared_http_client_is_created_once() -> None:
    async def scenario() -> None:
        bot = Bot()
        first = bot.http
        assert bot.http is first
        assert not first.closed
        await first.close()

    run(scenario())


def test_the_command_line_names_bots_precisely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    examples = Path(__file__).resolve().parent.parent / "examples"
    monkeypatch.syspath_prepend(str(examples))
    bot = load_bot("dice:Dice")
    assert isinstance(bot, Bot)
    with pytest.raises(InvalidArgument):
        load_bot("dice")
    with pytest.raises(InvalidArgument, match="не является подклассом sukarisebot.Bot"):
        load_bot("json:dumps")
    assert main(["no-colon-here"]) == 2
    assert main(["definitely_missing_module:Bot"]) == 2
    sys.modules.pop("dice", None)


def test_the_store_helper_is_exported_with_its_type_alias() -> None:
    import sukarisebot

    assert "JsonStore" in sukarisebot.__all__ and "load_bot" in sukarisebot.__all__


def test_a_write_that_fails_leaves_the_store_as_it_was(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = JsonStore(tmp_path / "data.json")
        await store.set("good", 1)
        with pytest.raises(TypeError):
            await store.set("bad", object())  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            await store.update("worse", lambda old: object())  # type: ignore[arg-type,return-value]
        assert await store.all() == {"good": 1}
        await store.set("later", 2)  # хранилище по-прежнему работает
        assert json.loads((tmp_path / "data.json").read_text(encoding="utf-8")) == {"good": 1, "later": 2}

    run(scenario())
