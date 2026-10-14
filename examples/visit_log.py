"""Помнит посетителей между запусками: сколько раз заходили и сколько писали.

Записи хранятся по ID игрока, поэтому тот, кто сменил имя, сохраняет свою
историю. Файл записывается атомарно, а работа с диском идёт вне цикла событий.

!visits    показать свои счётчики заходов и сообщений
"""

from pathlib import Path

from sukarisebot import Bot, Context, JsonStore, JsonValue, Location, User, command


def _count(old: JsonValue, username: str, field: str, amount: int) -> JsonValue:
    record: dict[str, JsonValue] = dict(old) if isinstance(old, dict) else {}
    current = record.get(field, 0)
    record[field] = (current if isinstance(current, int) else 0) + amount
    record["username"] = username
    return record


class VisitLog(Bot):
    def __init__(self, path: str | Path = "visit_log.json") -> None:
        super().__init__()
        self.store = JsonStore(path)

    async def on_user_join(self, user: User, position: Location) -> None:
        await self.store.update(user.id, lambda old: _count(old, user.username, "visits", 1))

    async def on_chat(self, user: User, message: str) -> None:
        await self.store.update(user.id, lambda old: _count(old, user.username, "messages", 1))

    @command("visits", description="ваши заходы и сообщения")
    async def visits(self, ctx: Context) -> None:
        record = await self.store.get(ctx.user.id)
        visits = record.get("visits", 0) if isinstance(record, dict) else 0
        messages = record.get("messages", 0) if isinstance(record, dict) else 0
        await ctx.reply(f"@{ctx.user.username}: заходов — {visits}, сообщений — {messages}.")


if __name__ == "__main__":
    VisitLog().start()
