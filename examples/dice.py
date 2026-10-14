"""Команды с ограничением частоты, псевдонимами и управлением только для владельца.

!roll          бросить шестигранный кубик (три броска в минуту на игрока)
!coins         подбросить монетку, без ограничений
!shutdown      только для владельца комнаты: попрощаться и остановить бота
"""

import random

from sukarisebot import Bot, Context, command


class Dice(Bot):
    @command("roll", aliases=("dice",), cooldown=(3, 60.0), description="бросить кубик")
    async def roll(self, ctx: Context) -> None:
        await ctx.reply(f"@{ctx.user.username} выбросил {random.randint(1, 6)}")

    @command("coins", description="подбросить монетку")
    async def coins(self, ctx: Context) -> None:
        await ctx.reply(random.choice(["орёл", "решка"]))

    @command("shutdown", owner_only=True, description="остановить бота")
    async def shutdown(self, ctx: Context) -> None:
        await ctx.reply("Ухожу спать. Пока!")
        await self.stop()


if __name__ == "__main__":
    Dice().start()
