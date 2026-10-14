"""Bot behaviour, driven through the in-memory harness (no server, no waiting)."""

from __future__ import annotations

import asyncio

import pytest

from sukarisebot import (
    Bot,
    ChatEvent,
    Context,
    InvalidArgument,
    Location,
    Position,
    SessionMetadata,
    User,
    command,
    every,
    split_message,
)
from sukarisebot.commands import Command, Commands
from sukarisebot.limits import Limiter
from sukarisebot.models import RateLimit
from sukarisebot.testing import Harness


def run(coro: object) -> None:
    asyncio.run(coro)  # type: ignore[arg-type]


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Welcome, {user.username}!")


def test_handlers_run_and_chat_is_recorded() -> None:
    async def scenario() -> None:
        harness = Harness(Greeter())
        await harness.start()
        await harness.join("alice")
        assert harness.chats == ["Welcome, alice!"]

    run(scenario())


def test_commands_answer_in_the_channel_they_came_from() -> None:
    class Shop(Bot):
        @command("hello", aliases=("hi",), description="say hello")
        async def hello(self, ctx: Context) -> None:
            await ctx.reply(f"hello {ctx.user.username}")

    async def scenario() -> None:
        harness = Harness(Shop())
        await harness.start()
        await harness.say("alice", "!hello")
        await harness.say("bob", "!HI", whisper=True)
        assert harness.chats == ["hello alice"]
        assert harness.whispers == ["hello bob"]

    run(scenario())


def test_command_arguments_are_split_for_you() -> None:
    seen: list[tuple[str, ...]] = []

    class Echo(Bot):
        @command("echo")
        async def echo(self, ctx: Context) -> None:
            seen.append(ctx.args)
            assert ctx.arg(0) == "first"
            assert ctx.arg(5) is None
            assert ctx.rest() == "first second"

    async def scenario() -> None:
        harness = Harness(Echo())
        await harness.start()
        await harness.say("alice", "!echo   first   second  ")
        assert seen == [("first", "second")]

    run(scenario())


def test_a_cooldown_limits_uses_per_user() -> None:
    class Dice(Bot):
        @command("roll", cooldown=(2, 60.0))
        async def roll(self, ctx: Context) -> None:
            await ctx.reply("4")

    async def scenario() -> None:
        harness = Harness(Dice())
        await harness.start()
        await harness.say("alice", "!roll")
        await harness.say("alice", "!roll")
        await harness.say("alice", "!roll")
        await harness.say("bob", "!roll")
        assert harness.chats[:2] == ["4", "4"]
        assert "подождите" in harness.chats[2] and "!roll" in harness.chats[2]
        assert harness.chats[3] == "4"

    run(scenario())


def test_owner_only_commands_refuse_everyone_else() -> None:
    class Admin(Bot):
        @command("lock", owner_only=True)
        async def lock(self, ctx: Context) -> None:
            await ctx.reply("locked")

    async def scenario() -> None:
        harness = Harness(Admin(), owner_id="owner-1")
        await harness.start()
        await harness.say("mallory", "!lock")
        assert harness.chats == ["@mallory, команда !lock только для владельца комнаты."]
        harness.requester.sent.clear()
        await harness.emit(ChatEvent(User("owner-1", "boss"), "!lock", whisper=False))
        assert harness.chats == ["locked"]

    run(scenario())


def test_help_lists_every_command_and_can_be_overridden() -> None:
    class Many(Bot):
        @command("alpha", description="first")
        async def alpha(self, ctx: Context) -> None:
            return None

        @command("beta")
        async def beta(self, ctx: Context) -> None:
            return None

    class Custom(Bot):
        @command("help")
        async def help(self, ctx: Context) -> None:
            await ctx.reply("my own help")

    async def scenario() -> None:
        harness = Harness(Many())
        await harness.start()
        await harness.say("alice", "!help")
        (text,) = harness.chats
        assert "!alpha - first" in text and "!beta" in text and "!help" in text
        custom = Harness(Custom())
        await custom.start()
        await custom.say("alice", "!help")
        assert custom.chats == ["my own help"]

    run(scenario())


def test_the_bot_never_answers_its_own_commands() -> None:
    calls: list[str] = []

    class Loop(Bot):
        @command("ping")
        async def ping(self, ctx: Context) -> None:
            calls.append(ctx.user.id)

    async def scenario() -> None:
        harness = Harness(Loop(), bot_id="bot-1")
        await harness.start()
        await harness.emit(ChatEvent(User("bot-1", "me"), "!ping", whisper=False))
        assert calls == []

    run(scenario())


def test_an_error_in_one_handler_reaches_on_error_and_the_next_event_still_runs() -> None:
    errors: list[str] = []

    class Fragile(Bot):
        async def on_chat(self, user: User, message: str) -> None:
            if message == "boom":
                raise ValueError("on purpose")
            await self.api.chat(f"got {message}")

        async def on_error(self, error: Exception, event: object) -> None:
            errors.append(str(error))

    async def scenario() -> None:
        harness = Harness(Fragile())
        await harness.start()
        await harness.say("alice", "boom")
        await harness.say("alice", "ok")
        assert errors == ["on purpose"]
        assert harness.chats == ["got ok"]

    run(scenario())


def test_wait_for_resolves_with_the_next_matching_reply() -> None:
    class Quiz(Bot):
        async def on_user_join(self, user: User, position: Location) -> None:
            await self.api.whisper(user.id, "What is 2 + 2?")
            answer = await self.wait_for(ChatEvent, lambda event: event.user.id == user.id, timeout=5)
            self.state["answer"] = answer.message

    async def scenario() -> None:
        bot = Quiz()
        harness = Harness(bot)
        await harness.start()
        join = asyncio.create_task(harness.join("alice"))
        await asyncio.sleep(0.01)
        await harness.say("bob", "4")  # somebody else answers first: ignored
        await harness.say("alice", "4", whisper=True)
        await join
        assert bot.state["answer"] == "4"

    run(scenario())


def test_every_runs_on_its_interval_while_connected() -> None:
    ticks: list[int] = []

    class Clock(Bot):
        @every(0.01)
        async def tick(self) -> None:
            ticks.append(1)

    async def scenario() -> None:
        bot = Clock()
        harness = Harness(bot)
        await harness.start()
        await asyncio.sleep(0.1)
        await bot._stop_schedules()
        assert len(ticks) >= 3

    run(scenario())


def test_a_long_message_is_split_into_chat_lines_and_nothing_is_lost() -> None:
    text = " ".join(f"word{i}" for i in range(200))

    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()
        await harness.bot.api.chat(text)
        assert len(harness.chats) > 1
        assert all(len(line) <= 500 for line in harness.chats)
        assert " ".join(harness.chats).split() == text.split()

    run(scenario())


def test_split_message_breaks_at_spaces_and_hard_cuts_long_words() -> None:
    assert split_message("abc def", limit=4) == ["abc", "def"]
    assert split_message("x" * 10, limit=4) == ["xxxx", "xxxx", "xx"]
    assert split_message("   ") == []


def test_invalid_arguments_are_refused_before_anything_is_sent() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()
        with pytest.raises(InvalidArgument):
            await harness.bot.api.chat("   ")
        with pytest.raises(InvalidArgument):
            await harness.bot.api.react("boo", "u1")  # type: ignore[arg-type]
        with pytest.raises(InvalidArgument):
            await harness.bot.api.move_to(Position(1e9, 0.0, 0.0))
        with pytest.raises(InvalidArgument):
            await harness.bot.api.moderate("u1", "ban", seconds=10**9)
        with pytest.raises(InvalidArgument):
            await harness.bot.api.channel("x", tags=["t" * 33])
        assert harness.requests("ChatRequest") == []
        assert harness.requests("ReactionRequest") == []

    run(scenario())


def test_moderation_shortcuts_send_the_right_action() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()
        await harness.bot.api.kick("u1")
        await harness.bot.api.ban("u2", seconds=3600)
        await harness.bot.api.mute("u3", 60)
        await harness.bot.api.unban("u2")
        actions = [
            (sent.body["user_id"], sent.body["moderation_action"], sent.body["action_length"])
            for sent in harness.requests("ModerateRoomRequest")
        ]
        assert actions == [("u1", "kick", None), ("u2", "ban", 3600), ("u3", "mute", 60), ("u2", "unban", None)]

    run(scenario())


def test_set_privileges_leaves_unspecified_rights_as_null() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()
        await harness.bot.api.set_privileges("u1", designer=True)
        (sent,) = harness.requests("ChangeRoomPrivilegeRequest")
        assert sent.body["permissions"] == {"moderator": None, "designer": True}

    run(scenario())


def test_gold_reads_the_wallet() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()
        harness.requester.gold = 75
        assert await harness.bot.api.gold() == 75

    run(scenario())


def test_the_room_roster_follows_joins_and_leaves() -> None:
    async def scenario() -> None:
        harness = Harness(Bot(), clean_room=True)
        await harness.start()
        alice = await harness.join("alice")
        assert alice in [entry.user for entry in harness.bot.room.users()]
        assert harness.bot.room.find("ALICE") is not None
        await harness.leave(alice)
        assert len(harness.bot.room) == 0

    run(scenario())


def test_user_state_is_kept_per_user() -> None:
    async def scenario() -> None:
        bot = Bot()
        bot.user_state("u1")["visits"] = 2
        assert bot.user_state("u1") == {"visits": 2}
        assert bot.user_state("u2") == {}

    run(scenario())


def test_a_bot_outside_a_connection_cannot_act() -> None:
    with pytest.raises(Exception, match="не запущен"):
        _ = Bot().api


def test_a_command_registered_twice_is_refused() -> None:
    commands = Commands()

    async def handler(ctx: Context) -> None:
        return None

    commands.add(Command(name="same", handler=handler))
    with pytest.raises(InvalidArgument, match="уже зарегистрирована"):
        commands.add(Command(name="same", handler=handler))


def test_a_bad_decorator_argument_fails_when_the_class_is_written() -> None:
    with pytest.raises(InvalidArgument):
        every(0)
    with pytest.raises(InvalidArgument):
        command("two words")


def test_the_limiter_paces_requests_instead_of_failing_them() -> None:
    async def scenario() -> None:
        limiter = Limiter({"chat": RateLimit(2, 0.5)})
        loop = asyncio.get_running_loop()
        started = loop.time()
        for _ in range(4):
            await limiter.acquire("chat")
        elapsed = loop.time() - started
        assert 0.2 <= elapsed <= 2.0

    run(scenario())


def test_session_metadata_is_available_to_handlers() -> None:
    async def scenario() -> None:
        harness = Harness(Bot(), owner_id="owner-7", room_name="Lobby")
        await harness.start()
        session = harness.bot.session
        assert isinstance(session, SessionMetadata)
        assert session.room_info.room_name == "Lobby"
        assert harness.bot.is_owner(User("owner-7", "boss"))

    run(scenario())


def test_a_failing_wait_check_reaches_the_code_that_waits() -> None:
    class Waiter(Bot):
        failure: str = ""

        async def on_chat(self, user: User, message: str) -> None:
            def broken(event: ChatEvent) -> bool:
                raise RuntimeError("the check is broken")

            try:
                await self.wait_for(ChatEvent, broken, timeout=5)
            except RuntimeError as error:
                self.failure = str(error)

    async def scenario() -> None:
        bot = Waiter()
        harness = Harness(bot)
        await harness.start()
        first = asyncio.create_task(harness.say("alice", "first"))
        await asyncio.sleep(0)
        await harness.say("bob", "second")
        await first
        assert bot.failure == "the check is broken"

    run(scenario())


def test_a_bot_can_replace_the_phrases_it_says_by_itself() -> None:
    from sukarisebot import Phrases

    class English(Bot):
        phrases = Phrases(
            owner_only="@{username}, {prefix}{command} is for the owner.",
            cooldown="@{username}, wait {seconds} s before {prefix}{command}.",
            help="Commands: {commands}",
            help_separator=" / ",
        )

        @command("lock", owner_only=True, description="lock it")
        async def lock(self, ctx: Context) -> None:
            await ctx.reply("locked")

        @command("ping", cooldown=(1, 60.0))
        async def ping(self, ctx: Context) -> None:
            await ctx.reply("pong")

    async def scenario() -> None:
        harness = Harness(English(), owner_id="owner-1")
        await harness.start()
        await harness.say("mallory", "!lock")
        await harness.say("alice", "!ping")
        await harness.say("alice", "!ping")
        await harness.say("alice", "!help")
        assert harness.chats[0] == "@mallory, !lock is for the owner."
        assert harness.chats[1] == "pong"
        assert harness.chats[2] == "@alice, wait 60 s before !ping."
        assert harness.chats[3] == "Commands: !lock - lock it / !ping / !help - список команд"  # по алфавиту имён методов, !help последней

    run(scenario())
