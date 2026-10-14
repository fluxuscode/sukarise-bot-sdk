"""Бот для чаевых: собирает их, помнит самых щедрых и отвечает в личных сообщениях.

Люди дают боту чаевые в его комнате, и бот получает их золотом. Это золото
владелец забирает на карточке бота в личном кабинете (кнопка «Забрать золото»).
Бот ведёт таблицу лидеров, которая переживает перезапуск, благодарит щедрых и
отвечает на команды владельца в чате, шёпотом и в личных сообщениях.

!top      десять самых щедрых
!wallet   сколько золота у бота
"""

from pathlib import Path

from sukarisebot import Bot, Context, CurrencyItem, Item, JsonStore, JsonValue, User, command

GENEROUS = 500  # чаевые от этой суммы бот благодарит вслух


def _add(old: JsonValue, username: str, amount: int) -> JsonValue:
    record: dict[str, JsonValue] = dict(old) if isinstance(old, dict) else {}
    total = record.get("total", 0)
    record["total"] = (total if isinstance(total, int) else 0) + amount
    record["username"] = username
    return record


class TippingBot(Bot):
    def __init__(self, path: str | Path = "tips.json") -> None:
        super().__init__()
        self.store = JsonStore(path)

    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        # В этом потоке и чаевые между другими людьми; считаем только чаевые боту.
        if self.session is None or receiver.id != self.session.user_id:
            return
        if not isinstance(item, CurrencyItem):
            return
        await self.store.update(sender.id, lambda old: _add(old, sender.username, item.amount))
        if item.amount >= GENEROUS:
            await self.api.chat(f"Спасибо, {sender.username}, за щедрые {item.amount} золота!")

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        """Личное сообщение: отвечаем только на команды владельца."""
        if not self.is_owner_id(user_id):
            return
        messages = await self.api.messages(conversation_id)
        if not messages:
            return
        answer = await self._answer(messages[0].content)
        if answer:
            await self.api.send_message(conversation_id, answer)

    def is_owner_id(self, user_id: str) -> bool:
        return self.owner_id is not None and user_id == self.owner_id

    @command("top", owner_only=True, description="самые щедрые")
    async def top(self, ctx: Context) -> None:
        await ctx.reply(await self._leaderboard())

    @command("wallet", owner_only=True, description="золото бота")
    async def wallet(self, ctx: Context) -> None:
        await ctx.reply(f"У меня {await self.api.gold()} золота.")

    async def _answer(self, text: str) -> str | None:
        match text.strip().lower().removeprefix("!"):
            case "top":
                return await self._leaderboard()
            case "wallet":
                return f"У меня {await self.api.gold()} золота."
            case _:
                return None

    async def _leaderboard(self) -> str:
        rows: list[tuple[int, str]] = []
        for record in (await self.store.all()).values():
            if isinstance(record, dict):
                total, name = record.get("total", 0), record.get("username", "?")
                if isinstance(total, int) and isinstance(name, str):
                    rows.append((total, name))
        if not rows:
            return "Чаевых пока никто не давал."
        rows.sort(reverse=True)
        return "Самые щедрые:\n" + "\n".join(f"{i}. {name} ({total})" for i, (total, name) in enumerate(rows[:10], 1))


if __name__ == "__main__":
    TippingBot().start()
