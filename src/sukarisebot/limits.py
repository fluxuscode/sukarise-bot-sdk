"""Клиентские «вёдра с жетонами», повторяющие лимиты сервера.

Запрос сверх бюджета не отправляется сразу, а ждёт своей очереди. Сервер всё
равно отказал бы ему, а отказ с повтором всегда дольше короткого ожидания.
Бюджеты сервер присылает при подключении (``SessionMetadata.rate_limits``).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping

from .models import RateLimit


class _Bucket:
    __slots__ = ("_capacity", "_rate", "_tokens", "_updated")

    def __init__(self, limit: RateLimit) -> None:
        self._capacity = float(limit.requests)
        self._rate = limit.requests / limit.seconds
        self._tokens = self._capacity
        self._updated = time.monotonic()

    def take(self) -> float:
        """Потратить один жетон. Вернуть 0, если потрачен, иначе — сколько секунд ждать."""
        now = time.monotonic()
        self._tokens = min(self._capacity, self._tokens + (now - self._updated) * self._rate)
        self._updated = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return 0.0
        return (1.0 - self._tokens) / self._rate


class Limiter:
    """По одному ведру на каждую категорию, о которой сервер сообщил в ``SessionMetadata``.

    Ведро вмещает ``requests`` жетонов и пополняется равномерно: ``requests``
    жетонов за ``seconds`` секунд. Запрос тратит один жетон; если жетонов нет,
    :meth:`acquire` ждёт нужное время. Категории, которой сервер не назвал,
    не ограничиваются.
    """

    def __init__(self, limits: Mapping[str, RateLimit]) -> None:
        """Создать ограничитель по бюджетам сервера.

        :param limits: категория → лимит; записи с нулевым бюджетом пропускаются.
        """
        self._buckets = {
            name: _Bucket(limit)
            for name, limit in limits.items()
            if limit.requests > 0 and limit.seconds > 0
        }

    async def acquire(self, category: str) -> None:
        """Дождаться своей очереди в категории и занять жетон.

        :param category: категория запроса: ``chat``, ``move``, ``info`` и т. д.
        """
        bucket = self._buckets.get(category)
        if bucket is None:
            return
        while (wait := bucket.take()) > 0.0:
            await asyncio.sleep(wait)
