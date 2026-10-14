"""Примеры входят в документацию, поэтому их тоже запускают тесты."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from sukarisebot import Bot, Position
from sukarisebot.testing import Harness

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(coro: object) -> None:
    asyncio.run(coro)  # type: ignore[arg-type]


def test_greeter_welcomes_arrivals() -> None:
    greeter = load("greeter")

    async def scenario() -> None:
        harness = Harness(greeter.Greeter())
        await harness.start()
        await harness.join("alice", Position(0.0, 0.0, 0.0))
        assert harness.chats == ["Добро пожаловать в комнату, alice!"]

    run(scenario())


def test_dice_rolls_are_limited_and_owner_only_commands_are_guarded() -> None:
    dice = load("dice")

    async def scenario() -> None:
        harness = Harness(dice.Dice(), owner_id="owner-1")
        await harness.start()
        for _ in range(4):
            await harness.say("alice", "!roll")
        assert sum(1 for line in harness.chats if "выбросил" in line) == 3
        await harness.say("mallory", "!shutdown")
        assert "владельца" in harness.chats[-1]

    run(scenario())


def test_quiz_accepts_the_right_whisper_only() -> None:
    quiz = load("quiz")

    async def scenario() -> None:
        bot: Bot = quiz.Quiz()
        harness = Harness(bot)
        await harness.start()
        task = asyncio.create_task(harness.say("alice", "!quiz"))
        await asyncio.sleep(0.01)
        await harness.say("alice", "42", whisper=True)
        await task
        assert "Верно" in harness.whispers[-1]
        assert bot.user_state("user-alice") == {"solved": True}

    run(scenario())


def test_tipping_bot_counts_tips_to_itself_and_answers_its_owner_in_a_private_message(tmp_path: Path) -> None:
    from sukarisebot import CurrencyItem, MessageEvent, User

    tipping = load("tipping_bot")
    owner_message = {
        "message_id": "m1",
        "conversation_id": "c1",
        "createdAt": None,
        "content": "!top",
        "sender_id": "owner-1",
        "category": "text",
    }

    async def scenario() -> None:
        harness = Harness(tipping.TippingBot(tmp_path / "tips.json"), bot_id="bot-1", owner_id="owner-1")
        harness.requester.message_frames = [owner_message]
        await harness.start()
        bot_user = User("bot-1", "bot")
        ann = User("user-ann", "ann")
        await harness.emit(harness.event_tip(ann, bot_user, CurrencyItem("gold", 600)))
        await harness.emit(harness.event_tip(ann, User("someone", "else"), CurrencyItem("gold", 5)))
        assert any("щедрые 600 золота" in line for line in harness.chats)

        await harness.emit(MessageEvent(user_id="owner-1", conversation_id="c1", is_new_conversation=False))
        answers = [str(s.body["content"]) for s in harness.requests("SendMessageRequest")]
        assert answers and "1. ann (600)" in answers[0]

        # На личное сообщение постороннего бот не отвечает.
        before = len(harness.requests("SendMessageRequest"))
        await harness.emit(MessageEvent(user_id="stranger", conversation_id="c2", is_new_conversation=True))
        assert len(harness.requests("SendMessageRequest")) == before

    run(scenario())


def test_clean_room_example_loads_the_room_on_start() -> None:
    clean = load("clean_room")

    async def scenario() -> None:
        # Пример запрашивает состав комнаты в on_start намеренно; больше этого никто не делает.
        harness = Harness(clean.Doorman(), clean_room=True)
        await harness.start()
        assert harness.bot.room.seeded
        assert harness.requests("GetRoomUsersRequest") and len(harness.requests("GetRoomUsersRequest")) == 1

    run(scenario())


@pytest.mark.parametrize("name", ["greeter", "dice", "quiz", "clean_room", "tips", "visit_log"])
def test_every_example_imports(name: str) -> None:
    assert load(name) is not None


def test_visit_log_remembers_visitors_between_runs(tmp_path: Path) -> None:
    visit_log = load("visit_log")
    path = tmp_path / "visits.json"

    async def first_visit() -> None:
        harness = Harness(visit_log.VisitLog(path))
        await harness.start()
        await harness.join("alice")
        await harness.say("alice", "hello")

    async def second_visit() -> None:
        harness = Harness(visit_log.VisitLog(path))
        await harness.start()
        await harness.join("alice")
        await harness.say("alice", "!visits")
        # Сам запрос !visits тоже сообщение в чате, поэтому он тоже посчитан.
        assert harness.whispers == [] and harness.chats[-1] == "@alice: заходов — 2, сообщений — 2."

    run(first_visit())
    run(second_visit())
