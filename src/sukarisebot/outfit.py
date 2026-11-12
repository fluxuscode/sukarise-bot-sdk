"""Правила наряда, которые проверяются на стороне SDK до отправки запроса.

Что можно надеть, окончательно решает сервер. Здесь ловятся типичные ошибки
заранее и с понятным текстом: нет части тела, две вещи одной категории или
сочетание, не закрывающее тело. Принадлежность вещей не проверяется — её знает
только сервер.

Категорию SDK читает из идентификатора, а сервер — из типа предмета в каталоге.
Идентификаторы ``bag-…`` бывают любого типа, поэтому SDK считает их «джокерами»
и не отказывает наряду, в котором такие предметы могут восполнить недостающее.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

from .models import Item

CLOTHING: str = "clothing"
"""Значение ``Item.type`` для одежды. Надеть можно только одежду."""

BODY_PARTS: frozenset[str] = frozenset(("body-flesh", "eye", "eyebrow", "nose", "mouth"))
"""Части тела, которые обязаны присутствовать в любом наряде: тело, глаза, брови, нос и рот."""

# Одно из этих сочетаний должно быть надето, иначе тело не закрыто.
COVERINGS: tuple[frozenset[str], ...] = (
    frozenset(("shirt", "pants")),
    frozenset(("shirt", "skirt")),
    frozenset(("dress",)),
    frozenset(("fullsuit",)),
)
"""Сочетания категорий, закрывающие тело: рубашка с брюками, рубашка с юбкой, платье, комбинезон."""

UNCLASSIFIED_PREFIX: str = "bag-"
"""Префикс идентификаторов, по которым тип предмета определить нельзя: под ним бывают бровь, рубашка, брюки и др."""

_CATEGORY = re.compile(r"^(body-flesh|eyebrow|eye|nose|mouth|shirt|pants|skirt|dress|fullsuit)(?:[-_]|$)")


def category_of(item_id: str) -> str | None:
    """Определить базовую категорию предмета по его идентификатору.

    Идентификатор начинается с названия категории (например,
    ``shirt-n_plaid_blackwhite`` — рубашка). Для аксессуаров и остального
    категории нет.

    :param item_id: идентификатор предмета из каталога.
    :returns: ``"shirt"``, ``"pants"``, ``"skirt"``, ``"dress"``, ``"fullsuit"``,
        ``"body-flesh"``, ``"eye"``, ``"eyebrow"``, ``"nose"`` или ``"mouth"``;
        ``None``, если предмет не относится к базовым категориям.
    """
    match = _CATEGORY.match(item_id)
    return match.group(1) if match else None


def outfit_problems(items: Sequence[Item]) -> list[str]:
    """Перечислить всё, что неверно в наряде как в целом.

    Проверяется: все предметы — одежда, ни один не повторяется, каждая базовая
    категория встречается не больше раза, на месте все части тела и тело закрыто.
    Именно эту проверку :meth:`BotAPI.wear` делает перед отправкой; её можно
    вызвать самому, чтобы не ловить исключение.

    :param items: предполагаемый наряд.
    :returns: тексты проблем; пустой список означает, что наряд верен.
    """
    problems: list[str] = []
    for item in items:
        if item.type != CLOTHING:
            problems.append(f"{item.id}: это не одежда, надевать можно только одежду")
    clothing = [item for item in items if item.type == CLOTHING]
    for item_id, count in Counter(item.id for item in clothing).items():
        if count > 1:
            problems.append(f"{item_id} указан несколько раз ({count}): предмет надевается один раз")
    present = Counter(category_of(item.id) for item in clothing)
    for category, count in sorted(present.items(), key=lambda pair: str(pair[0])):
        if category is not None and count > 1:
            problems.append(f"два предмета категории {category}: каждая базовая категория допускается один раз")
    worn = {category for category in present if category is not None}
    missing_parts = sorted(BODY_PARTS - worn)
    covered = any(covering <= worn for covering in COVERINGS)
    # Сервер определяет категорию по типу из каталога, а префикс ``bag-`` может скрывать любую
    # вещь (бровь, рубашку, брюки). Такие предметы SDK не классифицирует и не считает
    # нарушением то, что они способны восполнить: ошибка остаётся, только если их не хватает.
    unclassified = sum(1 for item in clothing if item.id.startswith(UNCLASSIFIED_PREFIX))
    still_needed = 0 if covered else min(len(covering - worn) for covering in COVERINGS)
    if unclassified < len(missing_parts) + still_needed:
        problems.extend(f"не хватает части тела: {part}" for part in missing_parts)
        if not covered:
            problems.append("тело не закрыто: наденьте рубашку и брюки, рубашку и юбку, платье или комбинезон")
    return problems
