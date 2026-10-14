"""Режим «чистой комнаты»: бот ничего не делает в комнате, пока этого не просит код.

При подключении он не запрашивает список людей, поэтому ``bot.room`` наполняется
по событиям входа. Полный список загружается по требованию:
``await bot.refresh_room()``.
"""

from sukarisebot import Bot, Context, Location, SessionMetadata, User, command


class Doorman(Bot):
    async def on_start(self, session: SessionMetadata) -> None:
        # Только здесь, намеренно, загружаем тех, кто уже в комнате.
        await self.refresh_room()

    async def on_user_join(self, user: User, position: Location) -> None:
        return None  # чистая комната: никаких приветствий, пока не попросят

    @command("who", description="перечислить людей в комнате")
    async def who(self, ctx: Context) -> None:
        names = ", ".join(entry.user.username for entry in self.room.users()) or "никого"
        await ctx.reply(f"В комнате: {names}")


if __name__ == "__main__":
    Doorman().start(clean_room=True)
