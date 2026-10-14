"""Команды чата: ``@command("имя")`` превращает метод бота в команду ``!имя``.

Команда срабатывает и в общем чате, и в шёпоте. Ответ ``ctx.reply`` уходит туда
же, откуда пришла команда: на шёпот отвечает шёпот. Префикс команд — ``!``.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .api import BotAPI
from .errors import InvalidArgument
from .models import User


@dataclass(frozen=True, slots=True)
class Context:
    """Один вызов команды: кто её вызвал, с чем и как ответить.

    Приходит единственным аргументом в метод, помеченный ``@command``.

    Пример (для сообщения ``!say привет всем``)::

        ctx.name   # "say"
        ctx.args   # ("привет", "всем")
        ctx.arg(0) # "привет"
        ctx.rest() # "привет всем"

    :ivar api: действия бота (то же, что ``self.api`` в боте).
    :ivar user: кто вызвал команду.
    :ivar name: каноническое имя команды (даже если вызвана по псевдониму), в нижнем регистре.
    :ivar args: слова после имени команды.
    :ivar whisper: команда пришла шёпотом.
    :ivar text: исходный текст сообщения целиком, с префиксом.
    """

    api: BotAPI
    """Действия бота; то же, что ``self.api`` внутри бота."""
    user: User
    """Кто вызвал команду."""
    name: str
    """Каноническое имя команды в нижнем регистре, даже если вызвана по псевдониму."""
    args: tuple[str, ...]
    """Слова после имени команды."""
    whisper: bool
    """``True``, если команда пришла шёпотом."""
    text: str
    """Исходный текст сообщения целиком, с префиксом."""

    def arg(self, index: int) -> str | None:
        """Получить аргумент по номеру.

        :param index: номер слова после имени команды; 0 — первое слово.
        :returns: слово или ``None``, если аргументов меньше.
        """
        return self.args[index] if index < len(self.args) else None

    def rest(self) -> str:
        """Получить всё после имени команды одной строкой.

        Лишние пробелы между словами схлопываются в один.

        :returns: аргументы через пробел; пустая строка, если их нет.
        """
        return " ".join(self.args)

    async def reply(self, message: str) -> None:
        """Ответить туда, откуда пришла команда: шёпотом на шёпот, в чат на реплику в чате.

        :param message: текст ответа; длинный текст режется на части.
        :raises InvalidArgument: текст пустой.
        :raises ResponseError: сервер отказал (например, получатель шёпота вышел из комнаты).
        """
        if self.whisper:
            await self.api.whisper(self.user.id, message)
        else:
            await self.api.chat(message)


type CommandHandler = Callable[[Context], Awaitable[None]]
"""Метод-команда: принимает :class:`Context` и ничего не возвращает."""


@dataclass(frozen=True, slots=True)
class Phrases:
    """Фразы, которые бот говорит от своего имени при работе с командами.

    По умолчанию русские. Чтобы заменить их, задайте в классе бота атрибут
    ``phrases``::

        class Greeter(Bot):
            phrases = Phrases(help="Commands: {commands}")

    В шаблонах можно использовать поля в фигурных скобках; перечень полей указан
    у каждого атрибута. Неизвестное поле приведёт к ``KeyError``, который
    попадёт в ``on_error``.

    :ivar owner_only: ответ, когда не владелец вызвал команду ``owner_only=True``.
        Поля: ``{username}``, ``{prefix}``, ``{command}``.
    :ivar cooldown: ответ, когда команду вызвали слишком часто.
        Поля: ``{username}``, ``{prefix}``, ``{command}``, ``{seconds}``.
    :ivar help: ответ на ``!help``. Поле: ``{commands}`` — список команд.
    :ivar help_separator: чем разделять команды в списке ``{commands}``.
    """

    owner_only: str = "@{username}, команда {prefix}{command} только для владельца комнаты."
    """Ответ не-владельцу на команду ``owner_only``. Поля: ``{username}``, ``{prefix}``, ``{command}``."""
    cooldown: str = "@{username}, подождите {seconds} с до следующего {prefix}{command}."
    """Ответ на слишком частый вызов. Поля: ``{username}``, ``{prefix}``, ``{command}``, ``{seconds}``."""
    help: str = "Команды: {commands}"
    """Ответ на ``!help``. Поле: ``{commands}``."""
    help_separator: str = "  |  "
    """Разделитель команд в списке ``!help``."""


@dataclass(slots=True)
class Command:
    """Описание одной зарегистрированной команды.

    Создаётся автоматически из метода с ``@command``; вручную нужен только в
    нестандартном коде, который собирает :class:`Commands` сам.

    :ivar name: имя без префикса.
    :ivar handler: асинхронная функция команды.
    :ivar aliases: другие имена той же команды.
    :ivar description: короткое описание для ``!help``.
    :ivar cooldown: ограничение частоты ``(число_вызовов, секунды)`` на игрока или ``None``.
    :ivar owner_only: команда только для владельца комнаты.
    """

    name: str
    """Имя команды без префикса."""
    handler: CommandHandler
    """Асинхронная функция, которая выполняет команду."""
    aliases: tuple[str, ...] = ()
    """Другие имена той же команды."""
    description: str = ""
    """Короткое описание, которое показывает ``!help``."""
    # (число вызовов, секунды): не больше стольких запусков одним игроком за любое такое окно.
    cooldown: tuple[int, float] | None = None
    """Ограничение ``(вызовов, секунд)`` на одного игрока или ``None``, если ограничения нет."""
    owner_only: bool = False
    """Команду может вызвать только владелец комнаты."""
    _uses: dict[str, deque[float]] = field(default_factory=dict[str, deque[float]])

    def usage(self, prefix: str) -> str:
        """Получить строку для ``!help``: ``!имя - описание``.

        :param prefix: префикс команд.
        :returns: имя с префиксом и, если есть, описание через « - ».
        """
        text = f"{prefix}{self.name}"
        return f"{text} - {self.description}" if self.description else text

    def admit(self, user_id: str, now: float) -> float:
        """Записать вызов игрока и проверить ограничение частоты.

        :param user_id: кто вызывает.
        :param now: текущее монотонное время в секундах.
        :returns: 0, если вызов разрешён; иначе — сколько секунд ждать.
        """
        if self.cooldown is None:
            return 0.0
        uses_allowed, window = self.cooldown
        uses = self._uses.setdefault(user_id, deque())
        while uses and now - uses[0] >= window:
            uses.popleft()
        if len(uses) < uses_allowed:
            uses.append(now)
            return 0.0
        return window - (now - uses[0])


def validate_command_name(name: str) -> str:
    """Проверить и нормализовать имя команды.

    :param name: имя; допускаются пробелы по краям и любой регистр.
    :returns: имя в нижнем регистре без пробелов по краям.
    :raises InvalidArgument: имя пусто или состоит из нескольких слов.
    """
    cleaned = name.strip().casefold()
    if not cleaned or any(char.isspace() for char in cleaned):
        raise InvalidArgument(f"имя команды — одно слово без пробелов, получено {name!r}")
    return cleaned


def validate_cooldown(cooldown: tuple[int, float] | None) -> tuple[int, float] | None:
    """Проверить ограничение частоты ``(вызовов, секунд)``.

    :param cooldown: пара или ``None``.
    :returns: то же значение, если оно верно.
    :raises InvalidArgument: вызовов меньше одного либо окно не положительное конечное число.
    """
    if cooldown is None:
        return None
    uses_allowed, window = cooldown
    if uses_allowed < 1 or not math.isfinite(window) or window <= 0:
        raise InvalidArgument("ограничение частоты — это (вызовов, секунд): вызовов не меньше 1, секунд больше 0")
    return cooldown


class Commands:
    """Реестр команд бота и их диспетчер.

    Создаётся самим :class:`Bot`; у бота он доступен только изнутри. Поведение
    описано в ``docs/commands.md``.
    """

    def __init__(self, prefix: str = "!", phrases: Phrases | None = None) -> None:
        """Создать пустой реестр.

        :param prefix: префикс команд; один символ или слово без пробелов.
        :param phrases: фразы бота; по умолчанию русские.
        :raises InvalidArgument: префикс пуст или содержит пробелы.
        """
        if not prefix or prefix.strip() != prefix or any(char.isspace() for char in prefix):
            raise InvalidArgument("префикс команд — непустой символ или слово без пробелов")
        self.prefix = prefix
        """Префикс команд; по умолчанию ``!``."""
        self.phrases = Phrases() if phrases is None else phrases
        """Фразы, которыми бот отвечает на отказ, слишком частый вызов и ``!help``."""
        self._by_name: dict[str, Command] = {}
        self._commands: list[Command] = []

    def add(self, command: Command) -> None:
        """Зарегистрировать команду под её именем и псевдонимами.

        Имена приводятся к нижнему регистру.

        :param command: команда.
        :raises InvalidArgument: имя или псевдоним неверны либо уже заняты.
        """
        command.name = validate_command_name(command.name)
        command.aliases = tuple(validate_command_name(alias) for alias in command.aliases)
        command.cooldown = validate_cooldown(command.cooldown)
        for name in (command.name, *command.aliases):
            if name in self._by_name:
                raise InvalidArgument(f"команда {name!r} уже зарегистрирована")
        for name in (command.name, *command.aliases):
            self._by_name[name] = command
        self._commands.append(command)

    def has(self, name: str) -> bool:
        """Проверить, есть ли команда (или псевдоним) с таким именем, без учёта регистра."""
        return name.casefold() in self._by_name

    def listing(self) -> list[Command]:
        """Получить команды в порядке регистрации (для ``!help``)."""
        return list(self._commands)

    async def dispatch(
        self,
        api: BotAPI,
        user: User,
        text: str,
        *,
        whisper: bool,
        is_owner: bool,
    ) -> bool:
        """Выполнить команду, которую задаёт ``text``.

        Проверяет префикс, находит команду, применяет ``owner_only`` и ограничение
        частоты, затем вызывает обработчик. Отказ и «подождите» бот говорит сам.

        :param api: действия бота.
        :param user: кто написал.
        :param text: текст сообщения.
        :param whisper: сообщение пришло шёпотом.
        :param is_owner: автор — владелец комнаты.
        :returns: ``False``, если ``text`` не команда; ``True``, если команда
            найдена (выполнена или отклонена).
        """
        if not text.startswith(self.prefix):
            return False
        words = text[len(self.prefix) :].split()
        if not words:
            return False
        name = words[0].casefold()
        command = self._by_name.get(name)
        if command is None:
            return False
        context = Context(api=api, user=user, name=command.name, args=tuple(words[1:]), whisper=whisper, text=text)
        if command.owner_only and not is_owner:
            await context.reply(
                self.phrases.owner_only.format(username=user.username, prefix=self.prefix, command=command.name)
            )
            return True
        wait = command.admit(user.id, time.monotonic())
        if wait > 0:
            await context.reply(
                self.phrases.cooldown.format(
                    username=user.username, prefix=self.prefix, command=command.name, seconds=math.ceil(wait)
                )
            )
            return True
        await command.handler(context)
        return True
