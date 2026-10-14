"""Состав комнаты, который SDK поддерживает по событиям. Код бота его читает, пишет только сам бот.

В начале соединения состав пуст. SDK сразу заполняет его с сервера, если бот не
запущен в режиме «чистой комнаты». В этом режиме ``seeded`` остаётся ``False``
до тех пор, пока бот сам не вызовет ``await bot.refresh_room()``, а до тех пор
в составе только те, кого бот видел входящими.
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import Location, RoomUser, User


class Room:
    """Кто сейчас в комнате и где находится.

    Доступен как ``bot.room``. Объект только для чтения: менять его из кода бота
    не нужно.

    **Что обновляет состав.** SDK получает от сервера только те события, для
    которых в боте переопределён обработчик. Поэтому состав следит за входами,
    выходами и перемещениями, только если бот переопределяет ``on_user_join``,
    ``on_user_leave`` и ``on_user_move`` (тело может быть пустым: ``pass``).
    Если бот переопределяет лишь часть из них, остальные изменения в составе не
    отражаются. Без этих обработчиков состав остаётся снимком, сделанным при
    подключении; обновить его полностью можно в любой момент вызовом
    ``await bot.refresh_room()``.

    Пример::

        entry = self.room.find("@Alice")
        if entry is not None:
            await self.api.whisper(entry.user.id, "Привет!")
    """

    def __init__(self) -> None:
        """Создать пустой состав. Вручную это делать не нужно: комната есть у каждого бота."""
        self._users: dict[str, RoomUser] = {}
        self._seeded = False

    @property
    def seeded(self) -> bool:
        """``True``, когда в составе все, кто в комнате, а не только увиденные входящими.

        В режиме «чистой комнаты» остаётся ``False``, пока бот не вызовет
        ``await bot.refresh_room()``.
        """
        return self._seeded

    def users(self) -> list[RoomUser]:
        """Все, кто сейчас в комнате, с их положением.

        :returns: новый список; его изменение на состав комнаты не влияет.
        """
        return list(self._users.values())

    def get(self, user_id: str) -> RoomUser | None:
        """Найти человека по идентификатору.

        :param user_id: идентификатор аккаунта.
        :returns: запись о человеке или ``None``, если его нет в комнате.
        """
        return self._users.get(user_id)

    def find(self, username: str) -> RoomUser | None:
        """Найти человека по имени без учёта регистра и ведущего ``@``.

        :param username: имя в игре, можно с ``@``: ``"Alice"``, ``"@alice"``.
        :returns: запись о человеке или ``None``, если такого имени в комнате нет.
        """
        wanted = username.removeprefix("@").casefold()
        for entry in self._users.values():
            if entry.user.username.casefold() == wanted:
                return entry
        return None

    def __contains__(self, user_id: object) -> bool:
        """Проверить, есть ли в комнате человек с таким идентификатором: ``user_id in bot.room``."""
        return isinstance(user_id, str) and user_id in self._users

    def __len__(self) -> int:
        """Сколько людей в комнате (с учётом самого бота, если сервер его вернул): ``len(bot.room)``."""
        return len(self._users)

    # ---- пишет только Bot -----------------------------------------------------

    def _reset(self) -> None:
        self._users.clear()
        self._seeded = False

    def _seed(self, users: Iterable[RoomUser]) -> None:
        self._users = {entry.user.id: entry for entry in users}
        self._seeded = True

    def _join(self, user: User, location: Location) -> None:
        self._users[user.id] = RoomUser(user, location)

    def _move(self, user: User, location: Location) -> None:
        self._users[user.id] = RoomUser(user, location)

    def _leave(self, user_id: str) -> None:
        self._users.pop(user_id, None)
