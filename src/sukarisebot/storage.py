"""Небольшое постоянное хранилище для данных бота: один JSON-файл, запись атомарна.

Ключи — строки по вашему выбору, например идентификатор игрока (но не имя:
имена меняются). Значения — JSON-значения. Каждая запись идёт во временный файл,
который затем заменяет старый, поэтому сбой посреди записи не оставит
наполовину записанный файл. Дисковые операции выполняются в рабочем потоке,
так что цикл событий продолжает обслуживать комнату.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
"""Любое значение, которое можно сохранить в JSON: ``None``, число, строка, список или словарь."""


class JsonStore:
    """Постоянный словарь «ключ → JSON-значение» в одном файле.

    Файл читается один раз при первом обращении и держится в памяти; каждое
    изменение сразу записывается на диск целиком. Подходит для небольших
    данных (счётчики, настройки, таблица лидеров), но не для больших баз.

    Одновременные изменения не теряются: :meth:`set` и :meth:`update`
    выстраиваются в очередь. Если файл уже существует, он должен содержать
    JSON-объект, иначе первое обращение выбросит ``ValueError``.

    Пример::

        store = JsonStore("visits.json")
        await store.set("user-1", {"visits": 1})
        record = await store.get("user-1")
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        """Подготовить хранилище. Файл не читается и не создаётся до первого обращения.

        :param path: путь к JSON-файлу; недостающие каталоги создаются при записи.
        """
        self._path = Path(path)
        self._lock = asyncio.Lock()
        self._data: dict[str, JsonValue] | None = None

    @property
    def path(self) -> Path:
        """Путь к файлу хранилища."""
        return self._path

    async def get(self, key: str, default: JsonValue = None) -> JsonValue:
        """Прочитать значение по ключу.

        :param key: ключ.
        :param default: что вернуть, если ключа нет.
        :returns: сохранённое значение или ``default``.
        :raises ValueError: файл существует, но в нём не JSON-объект.
        """
        data = await self._loaded()
        return data.get(key, default)

    async def all(self) -> dict[str, JsonValue]:
        """Получить копию всех записей, например для таблицы лидеров.

        :returns: словарь «ключ → значение»; его изменение хранилище не меняет.
        :raises ValueError: файл существует, но в нём не JSON-объект.
        """
        return dict(await self._loaded())

    async def set(self, key: str, value: JsonValue) -> None:
        """Записать значение и сохранить файл.

        :param key: ключ.
        :param value: JSON-значение; обычные Python-объекты (кроме словарей,
            списков, строк, чисел, ``bool`` и ``None``) не сохраняются.
        :raises ValueError: файл существует, но в нём не JSON-объект.
        :raises TypeError: значение нельзя записать в JSON.
        """
        async with self._lock:
            data = await self._loaded()
            await asyncio.to_thread(self._write, {**data, key: value})
            data[key] = value  # в памяти значение появляется только после успешной записи: неверное не должно там остаться

    async def update(
        self,
        key: str,
        change: Callable[[JsonValue], JsonValue],
        default: JsonValue = None,
    ) -> JsonValue:
        """Заменить значение ключа результатом ``change(старое значение)`` и вернуть новое.

        Чтение, изменение и запись выполняются под одним замком, поэтому
        одновременные обновления одного ключа не затирают друг друга.

        :param key: ключ.
        :param change: функция «старое значение → новое».
        :param default: старое значение для функции, если ключа ещё нет.
        :returns: новое значение.
        :raises ValueError: файл существует, но в нём не JSON-объект.
        :raises TypeError: новое значение нельзя записать в JSON.
        """
        async with self._lock:
            data = await self._loaded()
            new = change(data.get(key, default))
            await asyncio.to_thread(self._write, {**data, key: new})
            data[key] = new
            return new

    async def _loaded(self) -> dict[str, JsonValue]:
        if self._data is None:
            self._data = await asyncio.to_thread(self._read)
        return self._data

    def _read(self) -> dict[str, JsonValue]:
        if not self._path.exists():
            return {}
        text = self._path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        value = cast(object, json.loads(text))
        if not isinstance(value, dict):
            raise ValueError(f"{self._path} должен содержать JSON-объект")
        return cast(dict[str, JsonValue], value)

    def _write(self, data: dict[str, JsonValue]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self._path.parent, prefix=self._path.name, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)
            raise
