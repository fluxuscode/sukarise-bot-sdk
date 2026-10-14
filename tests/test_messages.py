"""Tips and direct messages, driven through the in-memory harness."""

from __future__ import annotations

import asyncio

import pytest

from sukarisebot import Bot, InvalidArgument, MessageEvent
from sukarisebot.testing import Harness


def run(coro: object) -> None:
    asyncio.run(coro)  # type: ignore[arg-type]


MESSAGE: dict[str, object] = {
    "message_id": "m2",
    "conversation_id": "c1",
    "createdAt": "2026-10-14T10:00:00Z",
    "content": "hello bot",
    "sender_id": "user-ann",
    "category": "text",
}
CONVERSATION: dict[str, object] = {
    "id": "c1",
    "did_join": True,
    "unread_count": 1,
    "last_message": MESSAGE,
    "muted": False,
    "member_ids": ["bot-1", "user-ann"],
    "name": None,
    "owner_id": "user-ann",
}


class Answerer(Bot):
    """The documented tipping-bot pattern: read the new message, answer into it."""

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        messages = await self.api.messages(conversation_id)
        await self.api.send_message(conversation_id, f"you said: {messages[0].content}")


def test_a_message_event_reaches_on_message_and_the_bot_answers_into_the_conversation() -> None:
    async def scenario() -> None:
        harness = Harness(Answerer())
        harness.requester.message_frames = [MESSAGE]
        await harness.start()

        await harness.emit(MessageEvent(user_id="user-ann", conversation_id="c1", is_new_conversation=True))

        sent = harness.requests("SendMessageRequest")
        assert [s.body["content"] for s in sent] == ["you said: hello bot"]
        assert sent[0].body["conversation_id"] == "c1"
        assert sent[0].body["type"] == "text"
        assert sent[0].category == "message"

    run(scenario())


def test_the_message_subscription_is_on_only_for_a_bot_that_handles_messages() -> None:
    assert "message" in Answerer()._subscriptions()  # pyright: ignore[reportPrivateUsage]
    assert "message" not in Bot()._subscriptions()  # pyright: ignore[reportPrivateUsage]


def test_conversations_and_messages_are_parsed_into_typed_values() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        harness.requester.conversation_frames = [CONVERSATION]
        harness.requester.message_frames = [MESSAGE]
        await harness.start()

        page = await harness.bot.api.conversations()
        messages = await harness.bot.api.messages("c1", last_message_id="m9")

        assert page.not_joined == 0
        conversation = page.conversations[0]
        assert (conversation.id, conversation.did_join, conversation.unread_count) == ("c1", True, 1)
        assert conversation.member_ids == ("bot-1", "user-ann")
        assert conversation.last_message is not None and conversation.last_message.content == "hello bot"
        assert messages[0].sender_id == "user-ann" and messages[0].category == "text"
        assert harness.requests("GetMessagesRequest")[0].body["last_message_id"] == "m9"

    run(scenario())


def test_a_long_answer_is_split_into_messages() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()

        await harness.bot.api.send_message("c1", ("word " * 400).strip())

        sent = harness.requests("SendMessageRequest")
        assert len(sent) > 1
        assert all(len(str(s.body["content"])) <= 1000 for s in sent)

    run(scenario())


def test_bulk_messages_and_leaving_are_checked_before_anything_is_sent() -> None:
    async def scenario() -> None:
        harness = Harness(Bot(), clean_room=True)
        await harness.start()

        await harness.bot.api.send_bulk_message(["user-ann", "user-bob"], "news")
        await harness.bot.api.leave_conversation("c1")
        with pytest.raises(InvalidArgument):
            await harness.bot.api.send_bulk_message([], "news")
        with pytest.raises(InvalidArgument):
            await harness.bot.api.send_bulk_message(["u"] * 101, "news")
        with pytest.raises(InvalidArgument):
            await harness.bot.api.send_message("", "x")

        assert [s.kind for s in harness.requester.sent] == ["SendBulkMessageRequest", "LeaveConversationRequest"]

    run(scenario())


def test_a_purchase_is_paid_or_reports_missing_gold_without_raising() -> None:
    async def scenario() -> None:
        harness = Harness(Bot(), clean_room=True)
        await harness.start()

        assert await harness.bot.api.buy_item("shirt-n_cheap") is True
        harness.requester.tips_paid = False
        assert await harness.bot.api.buy_item("shirt-n_cheap") is False
        with pytest.raises(InvalidArgument):
            await harness.bot.api.buy_item("")

        bought = harness.requests("BuyItemRequest")
        assert [b.body["item_id"] for b in bought] == ["shirt-n_cheap", "shirt-n_cheap"]
        assert bought[0].category == "shop"

    run(scenario())


def test_a_tip_is_paid_or_reports_missing_gold_without_raising() -> None:
    async def scenario() -> None:
        harness = Harness(Bot())
        await harness.start()

        assert await harness.bot.api.tip("user-ann", "gold_bar_10") is True
        harness.requester.tips_paid = False
        assert await harness.bot.api.tip("user-ann", "gold_bar_10k") is False
        with pytest.raises(InvalidArgument):
            await harness.bot.api.tip("user-ann", "gold_bar_3")  # type: ignore[arg-type]

        tips = harness.requests("TipUserRequest")
        assert [t.body["gold_bar"] for t in tips] == ["gold_bar_10", "gold_bar_10k"]
        assert tips[0].category == "tip"

    run(scenario())
