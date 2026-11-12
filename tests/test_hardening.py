"""Checks added in 0.3.0 against the server's gateway (``internal/botapi`` in the server repo).

Each test pins one place where the SDK used to disagree with the server: a limit counted in
characters where the server counts bytes, a pre-check stricter than the server's, a refusal
the SDK now retries, a missing route that was retried forever, a command-line script that
could not find the bot's module.
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
from pathlib import Path

import pytest
from aiohttp.test_utils import TestServer
from fake_gateway import FakeGateway

import sukarisebot
from sukarisebot import (
    AnchorPosition,
    Bot,
    BotAPI,
    ConnectionRefused,
    InvalidArgument,
    Item,
    RateLimited,
    RecordingRequester,
    ResponseError,
    category_of,
    outfit_problems,
)
from sukarisebot.cli import main
from sukarisebot.commands import Command, Context
from sukarisebot.engine import Engine
from sukarisebot.models import SessionMetadata
from sukarisebot.testing import Harness

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "srbot_" + "b" * 64


def run(coro: object) -> None:
    asyncio.run(coro)  # type: ignore[arg-type]


def api() -> tuple[BotAPI, RecordingRequester]:
    requester = RecordingRequester()
    return BotAPI(requester), requester


async def noop_session(session: SessionMetadata) -> None:
    return None


async def noop_event(event: object) -> None:
    return None


def clothing(item_id: str) -> Item:
    return Item(type="clothing", amount=1, id=item_id)


BASE_BODY = ["body-flesh", "eye-n_basic", "eyebrow-n_basic", "nose-n_basic", "mouth-n_basic"]


# ---- limits that the server counts in bytes or bounds ---------------------------------


def test_a_channel_tag_is_limited_in_bytes_like_the_server() -> None:
    """The gateway refuses ``len(tag) > 32`` in Go, which is bytes: 17 Cyrillic letters are 34."""
    bot_api, requester = api()
    run(bot_api.channel("hi", tags=["я" * 16]))  # 32 bytes: allowed
    with pytest.raises(InvalidArgument):
        run(bot_api.channel("hi", tags=["я" * 17]))  # 34 bytes: the server would refuse
    assert len(requester.sent) == 1


def test_a_seat_number_outside_the_servers_range_is_refused_before_sending() -> None:
    bot_api, requester = api()
    run(bot_api.sit_on(AnchorPosition("chair-1", 255)))
    for bad in (-1, 256):
        with pytest.raises(InvalidArgument):
            run(bot_api.sit_on(AnchorPosition("chair-1", bad)))
    with pytest.raises(InvalidArgument):
        run(bot_api.sit_on(AnchorPosition("c" * 129, 0)))
    assert len(requester.sent) == 1


def test_identifiers_longer_than_the_servers_bounds_are_refused() -> None:
    bot_api, requester = api()
    with pytest.raises(InvalidArgument):
        run(bot_api.emote("e" * 97))
    with pytest.raises(InvalidArgument):
        run(bot_api.buy_item("i" * 257))
    with pytest.raises(InvalidArgument):
        run(bot_api.messages("c" * 129))
    run(bot_api.emote("e" * 96))
    run(bot_api.buy_item("i" * 256))
    assert [sent.kind for sent in requester.sent] == ["EmoteRequest", "BuyItemRequest"]


def test_buy_item_sends_the_trimmed_identifier() -> None:
    bot_api, requester = api()
    run(bot_api.buy_item("  shirt-n_basic  "))
    assert requester.sent[0].body == {"item_id": "shirt-n_basic"}


def test_an_outfit_of_more_than_sixty_four_items_is_refused() -> None:
    bot_api, _ = api()
    items = [clothing(item_id) for item_id in (*BASE_BODY, "shirt-a", "pants-a")]
    items += [clothing(f"hat-n_{index}") for index in range(60)]  # 67 in all
    with pytest.raises(InvalidArgument, match="64"):
        run(bot_api.wear(items))


# ---- the outfit pre-check must not refuse what the server accepts -------------------------


def test_a_bag_id_may_be_the_missing_eyebrow() -> None:
    """The server counts ``bag-n_elite2026dazzledbrows`` as an eyebrow by its catalog type."""
    items = [clothing(i) for i in ("body-flesh", "eye-n_basic", "nose-n_basic", "mouth-n_basic")]
    items += [clothing("bag-n_elite2026dazzledbrows"), clothing("shirt-a"), clothing("pants-a")]
    assert category_of("bag-n_elite2026dazzledbrows") is None
    assert outfit_problems(items) == []


def test_a_bag_id_may_be_the_shirt() -> None:
    items = [clothing(i) for i in BASE_BODY] + [clothing("bag-n_odd_shirt"), clothing("pants-a")]
    assert outfit_problems(items) == []


def test_a_missing_part_is_still_reported_when_the_bag_items_cannot_cover_it() -> None:
    items = [clothing(i) for i in ("body-flesh", "nose-n_basic", "mouth-n_basic", "shirt-a", "pants-a")]
    items.append(clothing("bag-n_one_thing"))  # may be the eyebrow or the eye, not both
    problems = outfit_problems(items)
    assert any("не хватает части тела" in problem for problem in problems)


def test_an_uncovered_body_without_bag_items_is_still_reported() -> None:
    items = [clothing(i) for i in BASE_BODY] + [clothing("shirt-a")]
    assert any("тело не закрыто" in problem for problem in outfit_problems(items))


def test_an_unrecognised_item_after_my_outfit_round_trip_is_not_blocked() -> None:
    """``wear(await my_outfit())`` is the common way to start; it must not fail on bag items."""
    worn = [clothing(i) for i in ("body-flesh", "eye-n_basic", "nose-n_basic", "mouth-n_basic")]
    worn += [clothing("bag-n_elite2026dazzledbrows"), clothing("bag-n_a_shirt"), clothing("pants-a")]
    bot_api, requester = api()
    run(bot_api.wear(worn))
    assert requester.sent[0].kind == "SetOutfitRequest"


# ---- the room follows arrivals and departures without handlers -----------------------------


def test_joins_and_leaves_are_subscribed_even_without_handlers() -> None:
    subscriptions = Bot()._subscriptions()  # pyright: ignore[reportPrivateUsage]
    assert {"chat", "user_joined", "user_left"} <= subscriptions
    assert "user_moved" not in subscriptions


def test_a_clean_room_subscribes_only_to_what_the_code_asked_for() -> None:
    assert Bot()._subscriptions(clean_room=True) == {"chat"}  # pyright: ignore[reportPrivateUsage]


# ---- a refusal for the rate limit is retried; it did not run ----------------------------------


def test_a_rate_limit_refusal_is_retried_and_then_succeeds() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(rate_limit_refusals={"ChatRequest": 2})
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions=(),
                on_session=noop_session,
                on_event=noop_event,
                rate_limit_pause=0.01,
            )
            task = asyncio.create_task(engine.run())
            while engine.session is None:
                await asyncio.sleep(0.01)
            await engine.request("ChatRequest", "chat", {"message": "hi", "whisper_target_id": None})
            chats = [frame for frame in gateway.requests if frame.get("_type") == "ChatRequest"]
            assert len(chats) == 3  # two refused, the third answered
            await engine.stop()
            await asyncio.wait_for(task, 5)

    run(scenario())


def test_a_rate_limit_refusal_that_keeps_coming_reaches_the_caller_as_rate_limited() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(rate_limit_refusals={"ChatRequest": 99})
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions=(),
                on_session=noop_session,
                on_event=noop_event,
                rate_limit_pause=0.01,
            )
            task = asyncio.create_task(engine.run())
            while engine.session is None:
                await asyncio.sleep(0.01)
            with pytest.raises(RateLimited) as caught:
                await engine.request("ChatRequest", "chat", {"message": "hi", "whisper_target_id": None})
            assert isinstance(caught.value, ResponseError)
            assert "Rate limit" in caught.value.message
            await engine.stop()
            await asyncio.wait_for(task, 5)

    run(scenario())


def test_another_refusal_is_not_retried() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(error_for={"ChatRequest": "The bot is muted"})
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions=(),
                on_session=noop_session,
                on_event=noop_event,
                rate_limit_pause=0.01,
            )
            task = asyncio.create_task(engine.run())
            while engine.session is None:
                await asyncio.sleep(0.01)
            with pytest.raises(ResponseError) as caught:
                await engine.request("ChatRequest", "chat", {"message": "hi", "whisper_target_id": None})
            assert not isinstance(caught.value, RateLimited)
            assert len([f for f in gateway.requests if f.get("_type") == "ChatRequest"]) == 1
            await engine.stop()
            await asyncio.wait_for(task, 5)

    run(scenario())


# ---- a route that stays missing is a wrong address, not a rollout --------------------------------


def test_a_gateway_that_keeps_answering_404_is_given_up_on() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(refuse_status=404)
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions=(),
                on_session=noop_session,
                on_event=noop_event,
                backoff_base=0.02,
                max_backoff=0.05,
                not_found_grace=0.3,
            )
            started = time.monotonic()
            with pytest.raises(ConnectionRefused, match="404"):
                await asyncio.wait_for(engine.run(), 10)
            assert time.monotonic() - started >= 0.3
            assert gateway.connections >= 2  # it did retry before giving up

    run(scenario())


def test_without_reconnect_a_temporary_http_refusal_is_raised_not_swallowed() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(refuse_status=503)
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions=(),
                on_session=noop_session,
                on_event=noop_event,
                reconnect=False,
            )
            with pytest.raises(ConnectionRefused) as caught:
                await asyncio.wait_for(engine.run(), 5)
            assert caught.value.do_not_reconnect is False
            assert "503" in caught.value.message

    run(scenario())


# ---- the command line ------------------------------------------------------------------------------


def test_the_script_finds_a_bot_module_in_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``sukarisebot`` script puts its own folder on sys.path, not the current one."""
    (tmp_path / "cwd_bot_module.py").write_text(
        "from sukarisebot import Bot\n\n\nclass Mine(Bot):\n    pass\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry not in ("", str(tmp_path))])
    monkeypatch.delitem(sys.modules, "cwd_bot_module", raising=False)
    started: list[Bot] = []
    monkeypatch.setattr(Bot, "start", lambda self, **_: started.append(self))
    assert main(["cwd_bot_module:Mine", "--room", "r", "--token", "t"]) == 0
    assert [type(bot).__name__ for bot in started] == ["Mine"]


def test_a_bad_log_level_is_a_usage_error_not_a_traceback() -> None:
    with pytest.raises(SystemExit) as caught:
        main(["x:Y", "--log-level", "LOUD"])
    assert caught.value.code == 2


# ---- command memory does not grow with every player ever seen --------------------------------------


def test_the_cooldown_table_forgets_players_whose_window_has_passed() -> None:
    async def handler(context: Context) -> None:
        return None

    command = Command(name="roll", handler=handler, cooldown=(1, 10.0))
    for index in range(1500):
        assert command.admit(f"user-{index}", float(index) * 0.001) == 0.0
    # all those calls were within the 10 s window; now move time forward past it
    assert command.admit("late", 100.0) == 0.0
    assert len(command._uses) < 1500  # pyright: ignore[reportPrivateUsage]


# ---- packaging ----------------------------------------------------------------------------------------


def test_the_package_version_matches_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.M)
    assert match is not None
    assert sukarisebot.__version__ == match.group(1)


def test_the_changelog_has_an_entry_for_the_current_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {sukarisebot.__version__} " in changelog


def test_harness_still_tracks_a_leave_without_handlers() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()
        user = await harness.join("alice")
        assert user.id in harness.bot.room
        await harness.leave(user)
        assert user.id not in harness.bot.room

    run(scenario())
