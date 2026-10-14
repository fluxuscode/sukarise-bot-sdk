"""Самый простой полезный бот: здоровается с каждым, кто вошёл в комнату.

Запуск (токен и ID комнаты можно взять из переменных окружения):

    SUKARISEBOT_TOKEN=srbot_... SUKARISEBOT_ROOM_ID=room-... python examples/greeter.py
"""

from sukarisebot import Bot, Location, User


class Greeter(Bot):
    async def on_user_join(self, user: User, position: Location) -> None:
        await self.api.chat(f"Добро пожаловать в комнату, {user.username}!")


if __name__ == "__main__":
    Greeter().start()
