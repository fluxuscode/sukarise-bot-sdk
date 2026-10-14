"""Integration tests: the SDK against a real websocket server (tests/fake_gateway.py)."""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from fake_gateway import FakeGateway
from sukarisebot import (
    Bot,
    ChatEvent,
    ConnectionRefused,
    Context,
    Event,
    RequestTimeout,
    ResponseError,
    SessionMetadata,
    User,
    command,
)
from sukarisebot.engine import Engine
from sukarisebot.models import Location

TOKEN = "srbot_" + "a" * 64
ALICE = {"id": "u1", "username": "alice"}
FRONT = {"x": 1, "y": 0, "z": 2, "facing": "FrontRight"}


async def wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached in time")
        await asyncio.sleep(0.01)


async def noop_session(session: SessionMetadata) -> None:
    return None


async def noop_event(event: Event) -> None:
    return None


class Greeter(Bot):
    def __init__(self) -> None:
        super().__init__()
        self.started = 0
        self.joined: list[str] = []

    async def on_start(self, session: SessionMetadata) -> None:
        self.started += 1
        await self.api.chat("hello room")

    async def on_user_join(self, user: User, position: Location) -> None:
        self.joined.append(user.username)


def test_the_handshake_sends_credentials_and_only_the_subscribed_events() -> None:
    async def scenario() -> None:
        gateway = FakeGateway()
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions={"emote", "chat"},
                on_session=noop_session,
                on_event=noop_event,
            )
            task = asyncio.create_task(engine.run())
            await wait_until(lambda: engine.session is not None)
            handshake = gateway.handshakes[0]
            assert (handshake.api_token, handshake.room_id) == (TOKEN, "room-9")
            assert handshake.query == "events=chat,emote"
            await engine.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_a_bot_seeds_its_room_and_greets_on_connect() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(room_content=[[ALICE, FRONT]])
        async with TestServer(gateway.app()) as server:
            bot = Greeter()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.started == 1)
            await wait_until(lambda: any(frame.get("_type") == "ChatRequest" for frame in gateway.requests))
            assert bot.room.seeded
            assert bot.room.find("@ALICE") is not None
            assert gateway.handshakes[0].query == "events=chat,user_joined"
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_clean_room_makes_no_request_the_bot_did_not_ask_for() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(room_content=[[ALICE, FRONT]])
        async with TestServer(gateway.app()) as server:
            bot = Greeter()
            task = asyncio.create_task(
                bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi")), clean_room=True)
            )
            await wait_until(lambda: bot.started == 1)
            assert not bot.room.seeded
            assert all(frame.get("_type") != "GetRoomUsersRequest" for frame in gateway.requests)
            await bot.refresh_room()
            assert bot.room.seeded and len(bot.room) == 1
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_a_refused_token_is_final() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(refuse_frame={"_type": "Error", "message": "this token is revoked", "do_not_reconnect": True})
        async with TestServer(gateway.app()) as server:
            with pytest.raises(ConnectionRefused, match="revoked") as refused:
                await Greeter().run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi")))
            assert refused.value.do_not_reconnect
            assert gateway.connections == 1

    asyncio.run(scenario())


def test_a_retryable_refusal_is_tried_again() -> None:
    async def scenario() -> None:
        retryable = {"_type": "Error", "message": "the room is not ready, try again shortly"}
        gateway = FakeGateway(refuse_frame=retryable, refuse_first_only=True)
        async with TestServer(gateway.app()) as server:
            bot = Greeter()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.started == 1)
            assert gateway.connections == 2
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_a_retryable_refusal_without_reconnect_raises_and_says_it_was_retryable() -> None:
    async def scenario() -> None:
        retryable = {"_type": "Error", "message": "the bot's owner needs an active PREMIUM subscription"}
        gateway = FakeGateway(refuse_frame=retryable)
        async with TestServer(gateway.app()) as server:
            with pytest.raises(ConnectionRefused, match="PREMIUM") as refused:
                await Greeter().run(
                    token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi")), reconnect=False
                )
            assert not refused.value.do_not_reconnect
            assert gateway.connections == 1

    asyncio.run(scenario())


def test_a_final_error_in_the_middle_of_a_session_ends_the_run() -> None:
    async def scenario() -> None:
        gateway = FakeGateway()
        async with TestServer(gateway.app()) as server:
            bot = Greeter()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.started == 1)
            await gateway.push({"_type": "Error", "message": "This bot connected from another place", "do_not_reconnect": True})
            with pytest.raises(ConnectionRefused, match="another place") as refused:
                await asyncio.wait_for(task, 5)
            assert refused.value.do_not_reconnect
            assert gateway.connections == 1

    asyncio.run(scenario())


def test_an_http_refusal_is_final() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(refuse_status=401)
        async with TestServer(gateway.app()) as server:
            with pytest.raises(ConnectionRefused, match="401"):
                await Greeter().run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi")))
            assert gateway.connections == 1

    asyncio.run(scenario())


def test_a_dropped_connection_is_redialled_and_the_bot_starts_again() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(drop_first_connection=True)
        async with TestServer(gateway.app()) as server:
            bot = Greeter()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.started == 2)
            assert gateway.connections >= 2
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_a_refused_request_raises_response_error_at_the_call_site() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(error_for={"ChatRequest": "message refused by test"})
        async with TestServer(gateway.app()) as server:
            bot = Greeter()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.started == 1)
            with pytest.raises(ResponseError, match="refused by test"):
                await bot.api.chat("hi")
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_every_event_kind_reaches_its_handler_over_the_wire() -> None:
    class Recorder(Bot):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[str] = []

        async def on_chat(self, user: User, message: str) -> None:
            self.seen.append(f"chat:{user.username}:{message}")

        async def on_whisper(self, user: User, message: str) -> None:
            self.seen.append(f"whisper:{user.username}:{message}")

        async def on_user_join(self, user: User, position: Location) -> None:
            self.seen.append(f"join:{user.username}")

        async def on_user_leave(self, user: User) -> None:
            self.seen.append(f"leave:{user.username}")

        async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None:
            self.seen.append(f"emote:{emote_id}")

        async def on_reaction(self, user: User, reaction: str, receiver: User) -> None:
            self.seen.append(f"reaction:{reaction}:{receiver.username}")

        async def on_channel(self, sender_id: str, message: str, tags: tuple[str, ...]) -> None:
            self.seen.append(f"channel:{sender_id}:{message}:{','.join(tags)}")

        async def on_moderate(self, moderator_id: str, target_user_id: str, moderation_type: str, duration: int | None) -> None:
            self.seen.append(f"moderate:{moderation_type}:{target_user_id}")

    async def scenario() -> None:
        gateway = FakeGateway()
        async with TestServer(gateway.app()) as server:
            bot = Recorder()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.connected)
            await gateway.push({"_type": "ChatEvent", "user": ALICE, "message": "hi", "whisper": False})
            await gateway.push({"_type": "ChatEvent", "user": ALICE, "message": "psst", "whisper": True})
            await gateway.push({"_type": "UserJoinedEvent", "user": ALICE, "position": FRONT})
            await gateway.push({"_type": "EmoteEvent", "user": ALICE, "emote_id": "wave", "receiver": None})
            await gateway.push({"_type": "ReactionEvent", "user": ALICE, "reaction": "heart", "receiver": {"id": "u2", "username": "bob"}})
            await gateway.push({"_type": "ChannelEvent", "sender_id": "bot-2", "msg": "ping", "tags": ["a"]})
            await gateway.push({"_type": "RoomModeratedEvent", "moderatorId": "owner-1", "targetUserId": "u2", "moderationType": "kick", "duration": None})
            await gateway.push({"_type": "UserLeftEvent", "user": ALICE})
            await wait_until(lambda: len(bot.seen) == 8)
            assert bot.seen == [
                "chat:alice:hi",
                "whisper:alice:psst",
                "join:alice",
                "emote:wave",
                "reaction:heart:bob",
                "channel:bot-2:ping:a",
                "moderate:kick:u2",
                "leave:alice",
            ]
            assert "u1" not in bot.room
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_a_silent_server_times_a_request_out() -> None:
    async def scenario() -> None:
        gateway = FakeGateway(silent=True)
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions=(),
                on_session=noop_session,
                on_event=noop_event,
                request_timeout=0.1,
            )
            task = asyncio.create_task(engine.run())
            await wait_until(lambda: engine.session is not None)
            with pytest.raises(RequestTimeout):
                await engine.request("GetWalletRequest", "info", {})
            await engine.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_keepalive_frames_are_sent_while_idle() -> None:
    async def scenario() -> None:
        gateway = FakeGateway()
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions=(),
                on_session=noop_session,
                on_event=noop_event,
                keepalive_interval=0.05,
            )
            task = asyncio.create_task(engine.run())
            await wait_until(lambda: any(frame.get("_type") == "KeepaliveRequest" for frame in gateway.requests))
            await engine.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_stopping_a_bot_returns_from_run() -> None:
    async def scenario() -> None:
        gateway = FakeGateway()
        async with TestServer(gateway.app()) as server:
            bot = Bot()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.connected)
            await bot.stop()
            await asyncio.wait_for(task, 5)
            assert not bot.connected

    asyncio.run(scenario())


def test_the_chat_subscription_is_always_present_for_commands() -> None:
    assert "chat" in Bot()._subscriptions()



def test_a_command_that_waits_for_a_reply_hears_it_over_the_wire() -> None:
    """The command holds the dispatcher while it waits, so the reply must not queue behind it."""

    class Asker(Bot):
        def __init__(self) -> None:
            super().__init__()
            self.answers: list[str] = []

        @command("ask")
        async def ask(self, ctx: Context) -> None:
            answer = await self.wait_for(ChatEvent, lambda event: event.whisper and event.user.id == ctx.user.id, timeout=2)
            self.answers.append(answer.message)

    async def scenario() -> None:
        gateway = FakeGateway()
        async with TestServer(gateway.app()) as server:
            bot = Asker()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.connected)
            await gateway.push({"_type": "ChatEvent", "user": ALICE, "message": "!ask", "whisper": False})
            await asyncio.sleep(0.05)
            started = time.monotonic()
            await gateway.push({"_type": "ChatEvent", "user": ALICE, "message": "42", "whisper": True})
            await wait_until(lambda: bot.answers == ["42"], timeout=1.5)
            assert time.monotonic() - started < 1.0
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_a_bot_is_not_connected_while_it_waits_to_reconnect() -> None:
    async def scenario() -> None:
        gateway = FakeGateway()
        async with TestServer(gateway.app()) as server:
            bot = Greeter()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: bot.started == 1)
            assert bot.connected and bot.session is not None
            first_session = bot.session
            await gateway.sockets[0].close()
            await wait_until(lambda: not bot.connected, timeout=1.0)  # пауза перед повтором — не меньше 0,25 с
            assert bot.session == first_session  # последняя известная сессия остаётся для уже стоящих в очереди событий
            await wait_until(lambda: bot.started == 2)
            assert bot.connected
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


async def serve_on(gateway: FakeGateway, port: int) -> web.AppRunner:
    runner = web.AppRunner(gateway.app())
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    return runner


def test_a_restarted_server_is_rejoined_by_the_bot() -> None:
    """The server restarts on the same address (a deploy): the bot waits, then starts again."""

    async def scenario() -> None:
        gateway = FakeGateway()
        port = free_port()
        runner = await serve_on(gateway, port)
        bot = Greeter()
        task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=f"ws://127.0.0.1:{port}/web/botapi"))
        try:
            await wait_until(lambda: bot.started == 1)
            await runner.cleanup()  # the server goes down under the open socket
            await asyncio.sleep(0.5)
            runner = await serve_on(gateway, port)
            await wait_until(lambda: bot.started == 2, timeout=15.0)
        finally:
            await bot.stop()
            await asyncio.wait_for(task, 5)
            await runner.cleanup()

    asyncio.run(scenario())


def test_a_silent_server_is_given_up_on_and_redialled() -> None:
    """A host that vanished without a reset sends nothing; the bot notices and redials."""

    async def scenario() -> None:
        gateway = FakeGateway(freeze_first_connection=True)
        async with TestServer(gateway.app()) as server:
            engine = Engine(
                url=str(server.make_url("/web/botapi")),
                token=TOKEN,
                room_id="room-9",
                subscriptions=(),
                on_session=noop_session,
                on_event=noop_event,
                keepalive_interval=0.05,
            )
            task = asyncio.create_task(engine.run())
            await wait_until(lambda: gateway.connections >= 2, timeout=15.0)
            await engine.stop()
            await asyncio.wait_for(task, 15)

    asyncio.run(scenario())


def test_a_missing_route_during_a_rollout_is_retried_not_final() -> None:
    """A 404 can come from a route that is absent for a moment; only a 401 or 403 is final."""

    async def scenario() -> None:
        gateway = FakeGateway(refuse_status=404)
        async with TestServer(gateway.app()) as server:
            bot = Greeter()
            task = asyncio.create_task(bot.run(token=TOKEN, room_id="room-9", url=str(server.make_url("/web/botapi"))))
            await wait_until(lambda: gateway.connections >= 2)
            gateway.refuse_status = None
            await wait_until(lambda: bot.started == 1, timeout=15.0)
            await bot.stop()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())
