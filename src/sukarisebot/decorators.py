"""Декораторы, которые помечают метод бота как команду чата или как таймер.

Пишутся прямо над методом, внутри класса бота::

    class Dice(Bot):
        @command("roll", cooldown=(3, 60), description="бросить кубик")
        async def roll(self, ctx: Context) -> None:
            await ctx.reply("4")

        @every(300)
        async def announce(self) -> None:
            await self.api.chat("Я всё ещё здесь!")

Пометки бот находит при создании; регистрировать ничего вручную не нужно.
Декоратор возвращает тот же метод без изменений, поэтому его можно вызывать
и напрямую, и подсказки редактора по параметрам сохраняются.
"""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Final, Protocol

from .commands import validate_command_name, validate_cooldown
from .errors import InvalidArgument

COMMAND_MARK: Final = "__sukarisebot_command__"
"""Имя атрибута, в который ``@command`` кладёт описание команды."""
EVERY_MARK: Final = "__sukarisebot_every__"
"""Имя атрибута, в который ``@every`` кладёт период таймера."""


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Описание команды, прикреплённое к методу декоратором :func:`command`.

    :ivar name: имя команды без префикса, в нижнем регистре.
    :ivar aliases: другие имена той же команды.
    :ivar description: короткое описание для ``!help``.
    :ivar cooldown: ограничение частоты ``(вызовов, секунд)`` на игрока или ``None``.
    :ivar owner_only: команда только для владельца комнаты.
    """

    name: str
    """Имя команды без префикса, в нижнем регистре."""
    aliases: tuple[str, ...]
    """Другие имена той же команды."""
    description: str
    """Короткое описание для ``!help``."""
    cooldown: tuple[int, float] | None
    """Ограничение ``(вызовов, секунд)`` на игрока или ``None``."""
    owner_only: bool
    """Команда только для владельца комнаты."""


class Marker(Protocol):
    """Декоратор, который возвращает полученный метод без изменений."""

    def __call__[F: Callable[..., Awaitable[None]]](self, func: F) -> F:
        """Пометить метод и вернуть его же.

        :param func: асинхронный метод бота.
        :returns: тот же метод.
        """
        ...


def command(
    name: str,
    *,
    aliases: Iterable[str] = (),
    description: str = "",
    cooldown: tuple[int, float] | None = None,
    owner_only: bool = False,
) -> Marker:
    """Сделать метод командой чата ``!имя`` для общего чата и шёпота.

    Метод принимает один аргумент — :class:`Context`. Регистр имени не важен:
    ``!Roll`` и ``!roll`` — одна команда. Команда ``!help`` создаётся
    автоматически; чтобы заменить её, объявите свою команду ``help``.

    Пример::

        @command("say", aliases=("echo",), description="повторить текст", cooldown=(2, 30))
        async def say(self, ctx: Context) -> None:
            await ctx.reply(ctx.rest() or "Что сказать?")

    :param name: имя команды: одно слово без пробелов.
    :param aliases: другие имена той же команды.
    :param description: описание для ``!help``.
    :param cooldown: ``(вызовов, секунд)`` — каждому игроку разрешено столько вызовов за окно;
        сверх этого бот просит подождать.
    :param owner_only: ``True`` — команду выполняет только владелец комнаты;
        остальным бот отвечает отказом.
    :returns: декоратор, который помечает метод.
    :raises InvalidArgument: имя или псевдоним пусты либо из нескольких слов,
        либо ограничение частоты неверно.
    """
    spec = CommandSpec(
        name=validate_command_name(name),
        aliases=tuple(validate_command_name(alias) for alias in aliases),
        description=description,
        cooldown=validate_cooldown(cooldown),
        owner_only=owner_only,
    )

    def mark[F: Callable[..., Awaitable[None]]](func: F) -> F:
        setattr(func, COMMAND_MARK, spec)
        return func

    return mark


def every(seconds: float) -> Marker:
    """Запускать метод каждые ``seconds`` секунд, пока бот подключён.

    Первый запуск — через ``seconds`` секунд после подключения (не сразу). Метод
    не принимает аргументов. Ошибка внутри метода не останавливает таймер: она
    уходит в :meth:`Bot.on_error`. При переподключении таймеры не
    перезапускаются, а продолжают идти; пока соединения нет, запуски пропускаются.

    Пример::

        @every(300)
        async def announce(self) -> None:
            await self.api.chat("Не забывайте про правила комнаты.")

    :param seconds: период в секундах; положительное конечное число.
    :returns: декоратор, который помечает метод.
    :raises InvalidArgument: период не положителен или не конечен.
    """
    if not math.isfinite(seconds) or seconds <= 0:
        raise InvalidArgument("период должен быть положительным числом секунд")

    def mark[F: Callable[..., Awaitable[None]]](func: F) -> F:
        setattr(func, EVERY_MARK, float(seconds))
        return func

    return mark
