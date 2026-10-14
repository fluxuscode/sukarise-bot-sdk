"""Командная строка: запустить бота из модуля, по аналогии с командой ``highrise``.

    python -m sukarisebot examples.dice:Dice --room ID_КОМНАТЫ --token srbot_...

Токен и комната можно передать и переменными окружения ``SUKARISEBOT_TOKEN`` и
``SUKARISEBOT_ROOM_ID``.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from collections.abc import Sequence

from .bot import Bot
from .errors import InvalidArgument, SukaRiseError


def load_bot(spec: str) -> Bot:
    """Создать бота по записи ``модуль:Класс``.

    Модуль импортируется обычным ``import``, поэтому он должен быть найден
    интерпретатором (лежать в текущем каталоге или в ``PYTHONPATH``).

    :param spec: например ``"examples.dice:Dice"``.
    :returns: новый бот (конструктор вызван без аргументов).
    :raises InvalidArgument: запись неверна или класс не наследует :class:`Bot`.
    :raises ImportError: модуль не найден.
    """
    module_name, separator, class_name = spec.partition(":")
    if not separator or not module_name or not class_name:
        raise InvalidArgument(f"укажите бота как модуль:Класс, получено {spec!r}")
    module = importlib.import_module(module_name)
    bot_class = getattr(module, class_name, None)
    if not (isinstance(bot_class, type) and issubclass(bot_class, Bot)):
        raise InvalidArgument(f"{spec} не является подклассом sukarisebot.Bot")
    return bot_class()


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа команды ``sukarisebot`` и ``python -m sukarisebot``.

    :param argv: аргументы командной строки; ``None`` — взять из ``sys.argv``.
    :returns: код завершения: 0 — штатно, 1 — сервер отказал, 2 — бот не найден.
    """
    parser = argparse.ArgumentParser(prog="sukarisebot", description="Запустить бота SukaRise.")
    parser.add_argument("bot", help="бот в виде модуль:Класс, например examples.dice:Dice")
    parser.add_argument("--room", dest="room_id", help="ID комнаты (или переменная SUKARISEBOT_ROOM_ID)")
    parser.add_argument("--token", help="токен бота (или переменная SUKARISEBOT_TOKEN)")
    parser.add_argument("--url", help="адрес шлюза (или переменная SUKARISEBOT_URL)")
    parser.add_argument("--clean-room", action="store_true", help="не делать запросов, которых не просил код бота")
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING или ERROR")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        bot = load_bot(args.bot)
    except (ImportError, InvalidArgument) as exc:
        print(f"sukarisebot: {exc}", file=sys.stderr)
        return 2
    try:
        bot.start(token=args.token, room_id=args.room_id, url=args.url, clean_room=args.clean_room)
    except SukaRiseError as exc:
        print(f"sukarisebot: {exc}", file=sys.stderr)
        return 1
    return 0
