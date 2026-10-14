"""Диалог: задать вопрос и дождаться ответа.

Игрок пишет !quiz; бот шёпотом задаёт вопрос и ждёт первый верный ответ от этого
игрока. На неверный ответ бот отвечает и продолжает ждать.

Пока бот ждёт ответ, он не обрабатывает другие события: ждущая команда держит
очередь обработчиков. Поэтому у ожидания всегда есть ``timeout``, а вызов команды
ограничен ``cooldown``. Для диалогов с несколькими игроками одновременно
запускайте каждый диалог отдельной задачей (см. docs/commands.md).
"""

from sukarisebot import Bot, ChatEvent, Context, command


class Quiz(Bot):
    @command("quiz", cooldown=(1, 30.0), description="ответить на вопрос")
    async def quiz(self, ctx: Context) -> None:
        await ctx.reply(f"@{ctx.user.username}, сколько будет 6 x 7? Вопрос пришлю шёпотом.")
        await ctx.api.whisper(ctx.user.id, "Сколько будет 6 x 7? Ответьте шёпотом.")
        for _ in range(3):
            answer = await self.wait_for(
                ChatEvent,
                lambda event: event.whisper and event.user.id == ctx.user.id,
                timeout=60,
            )
            if answer.message.strip() == "42":
                self.user_state(ctx.user.id)["solved"] = True
                await ctx.api.whisper(ctx.user.id, "Верно! Вам очко.")
                return
            await ctx.api.whisper(ctx.user.id, "Не совсем. Попробуйте ещё раз.")
        await ctx.api.whisper(ctx.user.id, "Попытки кончились. Напишите !quiz, чтобы начать заново.")


if __name__ == "__main__":
    Quiz().start()
