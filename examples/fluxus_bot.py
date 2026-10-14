"""Fluxus - ведущий вашей комнаты SukaRise: игры, профили, танцы, почта и характер.

Один файл, один бот. Он живёт в комнате как обычный гость и общается через чат,
шёпот и личные сообщения.

ЧТО УМЕЕТ
  Профили        уровни и титулы за активность, ежедневный бонус с серией, топы,
                 магазин титулов. Валюта бота - «искры»; к золоту игры они не имеют
                 отношения, золото бот получает только чаевыми.
  Игры           !dice !coin !slots !rps со ставками искрами, дуэль двух игроков
                 (!duel / !accept), викторина на всю комнату (!quiz), угадай число
                 (!guess), где подсказки видят все.
  Фишки          !8ball !roll !pick !ship !rate !who !joke !fact !praise !roast !hug.
  Тело           !dance, !party (вечеринка), !orbit, !come, !follow, !sit, а когда
                 никто не командует, бот сам бродит. В 2D-комнате он играет эмоции и
                 реакции, в 3D-мире (где сервер их ботам не даёт) танцует фигурами
                 по полу: круг, квадрат, зигзаг, звезда, орбита вокруг игрока.
                 Режим бот определяет сам.
  Общение        почта для тех, кого нет в комнате (!tell / !inbox), !seen, правила
                 комнаты, приветствие с учётом визитов, ответ на эмоции и реакции.
  Чаевые         золото, отданное боту, он благодарит и обменивает на искры
                 (чаевые доступны в 2D-комнатах: в 3D-мире сервер их не присылает).
  Личка          в личных сообщениях бот понимает: помощь, профиль, бонус, топ,
                 правила, почта.
  Владелец       !say !setrules !give !status !shutdown (только владельцу комнаты).

ЗАПУСК
  1. Установите SDK (из каталога sdk/python):   pip install -e .
  2. Задайте токен бота (из личного кабинета, раздел «Боты»):
         PowerShell:  $env:SUKARISEBOT_TOKEN = "srbot_..."
         bash:        export SUKARISEBOT_TOKEN=srbot_...
     Либо просто запустите файл: токен спросят при запуске (ввод скрыт).
  3. python fluxus_bot.py

  Бот должен быть добавлен в дизайнеры комнаты (настройки комнаты -> роли).
  Ответы на команды в шёпоте идут шёпотом, в общем чате - в общий чат.
  Данные (профили, почта, правила) лежат рядом с файлом: fluxus_data.json.

Переменные окружения: SUKARISEBOT_TOKEN, SUKARISEBOT_ROOM_ID, SUKARISEBOT_URL и
FLUXUS_DATA (путь к файлу данных, если он не должен лежать рядом с ботом).
Токен в файл не вписывайте: это пароль бота.
"""

from __future__ import annotations

import asyncio
import getpass
import hashlib
import logging
import math
import os
import random
import re
import sys
import time
from collections.abc import Awaitable
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from sukarisebot import (
    AnchorPosition,
    Bot,
    ConnectionRefused,
    Context,
    CurrencyItem,
    Item,
    JsonStore,
    JsonValue,
    Location,
    Position,
    Reaction,
    ResponseError,
    RoomUser,
    SessionMetadata,
    User,
    command,
    every,
)

# --------------------------------------------------------------------------------------
# Настройки
# --------------------------------------------------------------------------------------

DEFAULT_ROOM = "room-771927c72430c360"
# Шлюз ботов живёт на этом адресе; DEFAULT_URL в самом SDK указывает на сайт, а не на шлюз.
DEFAULT_URL = "wss://production-portal-refb.sukarise.ru/web/botapi"
DATA_FILE = Path(__file__).with_name("fluxus_data.json")

BOT_NAME = "Fluxus"
MSK = timezone(timedelta(hours=3))  # «сутки» для бонуса считаются по Москве

START_SPARKS = 100  # искры новичка
DAILY_BASE = 50  # ежедневный бонус
DAILY_STEP = 10  # прибавка за каждый день серии
DAILY_STEP_CAP = 10  # серия учитывается до 10 дней
XP_COOLDOWN = 30.0  # опыт за болтовню - не чаще, чем раз в столько секунд
VISIT_GAP = 600.0  # повторный вход раньше этого срока не считается новым визитом
MAX_STAKE = 500
GOLD_TO_SPARKS = 5  # одно золото, отданное боту чаевыми, - столько искр
MAIL_LIMIT = 5  # писем одному получателю
MAIL_LENGTH = 160
DUEL_TTL = 60.0
QUIZ_HINT_AFTER = 20.0
QUIZ_TIME = 45.0
GUESS_TIME = 120.0

LEVEL_TITLES: tuple[tuple[int, str], ...] = (
    (1, "Гость"),
    (3, "Завсегдатай"),
    (6, "Свой человек"),
    (10, "Душа комнаты"),
    (15, "Легенда"),
    (25, "Хранитель Flux"),
)

# Магазин титулов: ключ -> (название, цена в искрах).
SHOP: dict[str, tuple[str, int]] = {
    "joker": ("Весельчак", 300),
    "shadow": ("Тень", 500),
    "star": ("Звезда", 1000),
    "mage": ("Маг", 2000),
    "tycoon": ("Магнат", 5000),
}
SHOP_ALIASES: dict[str, str] = {
    "весельчак": "joker",
    "тень": "shadow",
    "звезда": "star",
    "маг": "mage",
    "магнат": "tycoon",
}

# Танцы без платы (бесплатные эмоции каталога). Ключ - то, что пишет игрок.
DANCES: dict[str, tuple[str, str]] = {
    "kpop": ("dance-blackpink", "K-Pop"),
    "kawaii": ("dance-kawai", "Kawaii Go Go"),
    "penguin": ("dance-pinguin", "Грувовый пингвин"),
    "russian": ("dance-russian", "Русский танец"),
    "savage": ("dance-tiktok8", "Savage"),
    "viral": ("dance-tiktok9", "Viral Groove"),
    "wop": ("dance-tiktok11", "Wop"),
    "shuffle": ("dance-tiktok10", "Shuffle"),
    "dontstart": ("dance-tiktok2", "Don't Start Now"),
    "saunter": ("dance-anime", "Saunter Sway"),
    "puppet": ("dance-creepypuppet", "Марионетка"),
    "pushit": ("dance-employee", "Push It"),
    "jingle": ("dance-jinglebell", "Jingle Hop"),
    "sweet": ("dance-touch", "Sweet Little Moves"),
}
DANCE_ALIASES: dict[str, str] = {
    "кпоп": "kpop",
    "кавай": "kawaii",
    "пингвин": "penguin",
    "русский": "russian",
    "кукла": "puppet",
    "марионетка": "puppet",
}
# Жесты: бот играет их сам, пока бродит по комнате.
GESTURES: tuple[tuple[str, str], ...] = (
    ("emote-bow", "поклон"),
    ("emote-curtsy", "реверанс"),
    ("emote-cutesalute", "милое приветствие"),
    ("emote-celebrate", "праздник"),
    ("emote-hyped", "азарт"),
    ("emote-flexing", "силач"),
    ("emote-frog", "лягушка"),
    ("emote-float", "левитация"),
)
WAVE = "emote-wave"
# В 3D-мире у бота нет эмоций (сервер их там не поддерживает), зато есть ходьба:
# танцует он фигурами по полу.
WALK_DANCES: dict[str, str] = {
    "circle": "Круг",
    "square": "Квадрат",
    "zigzag": "Зигзаг",
    "star": "Звезда",
    "orbit": "Орбита",
}
WALK_ALIASES: dict[str, str] = {
    "круг": "circle",
    "квадрат": "square",
    "зигзаг": "zigzag",
    "звезда": "star",
    "орбита": "orbit",
}
STEP_PAUSE = 1.3  # секунд между шагами танца-ходьбы
MOVE_CHECK = 0.9  # через сколько секунд после команды «иди» смотрим, сдвинулся ли бот
CLOSE_ENOUGH = 1.6  # ближе этого расстояния бот считает, что уже подошёл
# Точки рядом с человеком, куда бот пробует подойти (сервер молча игнорирует недостижимые).
APPROACH: tuple[tuple[float, float], ...] = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (0.0, 0.0))
REACTIONS: tuple[Reaction, ...] = ("heart", "clap", "wink", "wave", "thumbs")

# --------------------------------------------------------------------------------------
# Тексты
# --------------------------------------------------------------------------------------

NEW_GREETINGS = (
    "Добро пожаловать, {name}! Я {bot} - ведущий этой комнаты. Всё самое интересное: !help",
    "О, новое лицо! Привет, {name}. Сыграем? !help покажет, во что тут можно играть.",
    "{name}, добро пожаловать! Бонус новичка уже ждёт: напишите !daily.",
)
BACK_GREETINGS = (
    "С возвращением, {title} {name}! Это ваш {visit}-й визит.",
    "{name} снова с нами! Визит номер {visit}, {title}.",
    "Рад вас видеть, {name}! Визит {visit}, как время летит.",
)
OWNER_GREETINGS = (
    "Хозяин комнаты на месте! Здравствуйте, {name}.",
    "{name}, добро пожаловать домой! Комната в порядке, бот на посту.",
)
MENTION_REPLIES = (
    "Звали? Я тут. Команды: !help",
    "Слышу своё имя - значит, обо мне говорят хорошее.",
    "Я весь внимание, {name}.",
    "Fluxus на связи. Скучно? Попробуйте !quiz.",
)
BALL_ANSWERS = (
    "Бесспорно.", "Определённо да.", "Скорее да, чем нет.", "Знаки говорят: да.",
    "Пока не ясно, спросите позже.", "Лучше не рассказывать сейчас.", "Сосредоточьтесь и спросите ещё раз.",
    "Даже не думайте.", "Мой ответ - нет.", "Перспективы так себе.", "Весьма сомнительно.", "Конечно!",
)
JOKES = (
    "Почему программисты путают Хеллоуин и Рождество? Потому что 31 Oct = 25 Dec.",
    "Бот заходит в бар. Бармен: вам как обычно? Бот: у меня нет «обычно», у меня есть расписание.",
    "- Вы бот? - Нет, я виртуальный помощник. - А в чём разница? - Мы вежливее.",
    "Что ноль сказал восьмёрке? Классный пояс!",
    "Я не ленивый, я в режиме энергосбережения.",
    "Как называется бумеранг, который не возвращается? Палка.",
    "Почему у пингвинов смокинг? Потому что на айсберге нет химчистки.",
    "Хорошая новость: у меня всё под контролем. Плохая: контролем занимается кот.",
    "Мой Wi-Fi и я: мы просто потеряли связь.",
    "Сколько программистов нужно, чтобы вкрутить лампочку? Ни одного: это аппаратная проблема.",
)
FACTS = (
    "У осьминога три сердца.",
    "Сатурн настолько неплотный, что, будь на свете достаточно большой океан, он бы в нём плавал.",
    "С ботанической точки зрения банан - ягода, а клубника - нет.",
    "На Венере сутки длиннее года.",
    "Акулы появились раньше деревьев.",
    "Молния нагревает воздух вокруг себя сильнее, чем раскалена поверхность Солнца.",
    "У жирафа и человека одинаковое число шейных позвонков - семь.",
    "Первое SMS в истории отправили в 1992 году, и в нём было «Merry Christmas».",
    "Летом Эйфелева башня становится выше примерно на пятнадцать сантиметров: металл расширяется от тепла.",
    "Слово «робот» впервые прозвучало в пьесе Карела Чапека 1920 года.",
    "Земля слегка приплюснута у полюсов, так что она не идеальный шар.",
)
PRAISES = (
    "{name}, с вами в комнате становится светлее.",
    "{name}, у вас отличное чувство стиля.",
    "{name} - из тех, на кого хочется равняться.",
    "Если бы у комнаты был девиз, то им был бы {name}.",
    "{name}, вы делаете этот день лучше.",
    "{name} умеет появляться вовремя. Это талант.",
)
ROASTS = (
    "{name}, вы такой тихий, что даже Wi-Fi в лифте разговорчивее.",
    "{name}, у вас всё под контролем, как у котика на клавиатуре.",
    "{name}, вы не медленный - вы просто в режиме анимации.",
    "{name} ходит как на загрузке: вроде двигается, а прогресс не видно.",
    "{name}, если бы лень была видом спорта, вы бы проиграли, потому что не пришли.",
)
HUGS = (
    "{bot} обнимает {name}. Тёплое получилось объятие.",
    "{bot} крепко обнимает {name} - пикселями, но от души.",
    "Обнимашки для {name} доставлены!",
)
AMBIENT = (
    "Скучно? Напишите !quiz - угадаем что-нибудь вместе.",
    "Подсказка: !daily раз в сутки даёт искры, а за серию дней их больше.",
    "Хотите увидеть, как я танцую? !dance или сразу !party.",
    "Есть что сказать тому, кого нет в комнате? !tell имя текст.",
    "!duel имя ставка - вызовите кого-нибудь на дуэль.",
    "Загляните в !shop: искры можно обменять на титулы.",
    "Факт дня: {fact}",
    "Я {bot}, и я здесь, чтобы было интереснее. !help покажет всё, что я умею.",
)
DEFAULT_RULES = "В комнате действуют простые правила: будьте добры друг к другу, без спама и оскорблений. Приятного общения!"

HELP_OVERVIEW = (
    "Я {bot}. Разделы: !help игры | !help профиль | !help весело | !help бот | !help связь. "
    "Те же команды работают и шёпотом."
)
HELP_TOPICS: dict[str, str] = {
    "игры": (
        "Игры: !dice [ставка] - кубики против меня | !coin орёл/решка [ставка] | !slots [ставка] | "
        "!rps камень/ножницы/бумага [ставка] | !duel имя [ставка] и !accept | !quiz - викторина | "
        "!guess - угадай число. Ставка - искры, до {stake}, можно «все»."
    ),
    "профиль": (
        "Профиль: !me [имя] | !daily - бонус дня | !top [искры/уровень/викторина/щедрые] | "
        "!shop - титулы | !buy название | !title название или off. Опыт идёт за болтовню и игры."
    ),
    "весело": (
        "Веселье: !8ball вопрос | !roll 2d6 | !pick а, б, в | !ship имя [имя] | !rate что-то | "
        "!who кто-то там | !joke | !fact | !praise [имя] | !roast [имя] | !hug [имя]."
    ),
    "бот": (
        "Я в комнате: !dance [название] | !dances - список | !party - вечеринка | !orbit - покружить вокруг вас | "
        "!come - подойти | !follow - идти за вами | !stay - стоять | !sit - присесть рядом (в 2D)."
    ),
    "связь": (
        "Связь: !tell имя текст - письмо тому, кого нет рядом | !inbox - ваши письма | !seen имя | "
        "!rules - правила. Владельцу комнаты: !say !setrules !give !status !shutdown."
    ),
}
HELP_ALIASES: dict[str, str] = {
    "games": "игры", "profile": "профиль", "fun": "весело", "bot": "бот", "contact": "связь",
    "игра": "игры", "профили": "профиль", "веселье": "весело", "связи": "связь",
}

# Вопросы викторины: (вопрос, (ответ для показа, допустимые варианты...)).
QUIZ: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Столица Франции?", ("Париж",)),
    ("Самая большая планета Солнечной системы?", ("Юпитер",)),
    ("Как называется наша галактика?", ("Млечный Путь",)),
    ("Химический символ золота (две буквы)?", ("Au", "ау")),
    ("Сколько будет 12 x 12?", ("144", "сто сорок четыре")),
    ("Какая нелетающая птица живёт в Антарктиде?", ("Пингвин", "пингвины")),
    ("Столица Японии?", ("Токио",)),
    ("Самый большой океан на Земле?", ("Тихий", "тихий океан")),
    ("Сколько цветов у радуги?", ("7", "семь")),
    ("Чем мы дышим, чтобы жить? Назовите газ.", ("Кислород", "кислородом")),
    ("Кто написал роман «Война и мир»?", ("Толстой", "лев толстой")),
    ("Сколько минут в одном часе?", ("60", "шестьдесят")),
    ("Самое большое животное на планете?", ("Синий кит", "кит")),
    ("Сколько ног у паука?", ("8", "восемь")),
    ("Какой металл жидкий при комнатной температуре?", ("Ртуть",)),
    ("Как называется естественный спутник Земли?", ("Луна",)),
    ("Столица Италии?", ("Рим",)),
    ("Сколько сторон у шестиугольника?", ("6", "шесть")),
    ("Какой день недели идёт после вторника?", ("Среда", "среду")),
    ("Самая высокая гора мира?", ("Эверест", "джомолунгма")),
    ("Кто написал «Евгения Онегина»?", ("Пушкин", "александр пушкин")),
    ("Какая планета ближе всех к Солнцу?", ("Меркурий",)),
    ("Чему равно 2 в десятой степени?", ("1024",)),
    ("Сколько клавиш у стандартного пианино?", ("88", "восемьдесят восемь")),
    ("Какой язык программирования носит имя змеи и назван в честь британского комедийного шоу?", ("Python", "питон", "пайтон")),
    ("Столица Германии?", ("Берлин",)),
    ("Единица измерения силы тока?", ("Ампер", "ампера")),
    ("Сколько градусов в прямом угле?", ("90", "девяносто")),
    ("Какое животное называют «кораблём пустыни»?", ("Верблюд", "верблюда")),
    ("На каком языке говорят в Бразилии?", ("Португальский", "португальском")),
    ("Какая планета известна своими кольцами?", ("Сатурн",)),
    ("Сколько игроков одной команды одновременно на поле в футболе?", ("11", "одиннадцать")),
    ("Столица Великобритании?", ("Лондон",)),
    ("Какую планету называют красной?", ("Марс",)),
    ("Столица Испании?", ("Мадрид",)),
    ("Сколько дней в високосном году?", ("366", "триста шестьдесят шесть")),
    ("Основа гуакамоле - какой фрукт?", ("Авокадо",)),
    ("Загадка: зимой и летом одним цветом. Что это?", ("Ёлка", "ель", "елка")),
    ("Загадка: не лает, не кусает, а в дом не пускает.", ("Замок",)),
    ("Загадка: без окон, без дверей полна горница людей.", ("Огурец",)),
    ("Загадка: сидит дед во сто шуб одет, кто его раздевает, тот слёзы проливает.", ("Лук",)),
    ("Загадка: что можно увидеть с закрытыми глазами?", ("Сон", "сны")),
    ("Загадка: висит груша, нельзя скушать.", ("Лампочка", "лампа")),
    ("Как называется виртуальная валюта этого бота?", ("Искры", "искра")),
    ("Как зовут этого бота?", ("Fluxus", "флюкс", "флаксус")),
)

SLOT_REELS: tuple[tuple[str, int], ...] = (
    ("ВИШНЯ", 5),
    ("ЛИМОН", 5),
    ("СЛИВА", 5),
    ("ЗВЕЗДА", 3),
    ("СЕМЁРКА", 2),
)
SLOT_JACKPOT: dict[str, int] = {"ВИШНЯ": 5, "ЛИМОН": 5, "СЛИВА": 5, "ЗВЕЗДА": 15, "СЕМЁРКА": 25}

PLURAL_SPARKS = ("искра", "искры", "искр")

# --------------------------------------------------------------------------------------
# Мелкие помощники
# --------------------------------------------------------------------------------------


def plural(count: int, forms: tuple[str, str, str]) -> str:
    """Число со склонением: 1 искра, 2 искры, 5 искр."""
    n = abs(count) % 100
    if 11 <= n <= 14:
        form = forms[2]
    else:
        last = n % 10
        form = forms[0] if last == 1 else forms[1] if 2 <= last <= 4 else forms[2]
    return f"{count} {form}"


def sparks(count: int) -> str:
    return plural(count, PLURAL_SPARKS)


def normalize(text: str) -> str:
    """Нижний регистр, «ё» как «е», только буквы и цифры, пробелы схлопнуты."""
    lowered = text.casefold().replace("ё", "е")
    return " ".join(re.sub(r"[^0-9a-zа-я]+", " ", lowered).split())


def contains_phrase(message: str, phrase: str) -> bool:
    """Есть ли фраза в сообщении как набор слов подряд."""
    words, wanted = normalize(message).split(), normalize(phrase).split()
    if not wanted or len(wanted) > len(words):
        return False
    return any(words[i : i + len(wanted)] == wanted for i in range(len(words) - len(wanted) + 1))


def stable_percent(*names: str) -> int:
    """Одно и то же число 0..100 для одного и того же набора имён, независимо от порядка."""
    digest = hashlib.md5("|".join(sorted(name.casefold().lstrip("@") for name in names)).encode()).hexdigest()
    return int(digest[:8], 16) % 101


def ago(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 90:
        return "только что"
    if seconds < 3600:
        return plural(int(seconds // 60), ("минуту", "минуты", "минут")) + " назад"
    if seconds < 86400:
        return plural(int(seconds // 3600), ("час", "часа", "часов")) + " назад"
    return plural(int(seconds // 86400), ("день", "дня", "дней")) + " назад"


def moscow_day(offset_days: int = 0) -> str:
    return (datetime.now(MSK).date() + timedelta(days=offset_days)).isoformat()


def dance_path(style: str, center: Position) -> list[Position]:
    """Точки танца-ходьбы вокруг центра; последняя точка - возврат в центр."""
    cx, cz = center.x, center.z
    points: list[tuple[float, float]]
    if style == "square":
        points = [(cx + 1.4, cz + 1.4), (cx + 1.4, cz - 1.4), (cx - 1.4, cz - 1.4), (cx - 1.4, cz + 1.4)]
    elif style == "zigzag":
        points = [(cx + (1.5 if i % 2 == 0 else -1.5), cz + 0.7 * (i - 3)) for i in range(7)]
    elif style == "star":
        points = [
            (cx + 1.8 * math.cos(math.radians(90 + 144 * i)), cz + 1.8 * math.sin(math.radians(90 + 144 * i)))
            for i in range(5)
        ]
    else:
        count, radius = (12, 2.2) if style == "orbit" else (8, 1.6)
        points = [
            (cx + radius * math.cos(2 * math.pi * i / count), cz + radius * math.sin(2 * math.pi * i / count))
            for i in range(count)
        ]
    path = [Position(x, center.y, z, facing="FrontLeft") for x, z in points]
    return [*path, Position(cx, center.y, cz, facing="FrontRight")]


def level_title(level: int) -> str:
    title = LEVEL_TITLES[0][1]
    for threshold, name in LEVEL_TITLES:
        if level >= threshold:
            title = name
    return title


# --------------------------------------------------------------------------------------
# Данные
# --------------------------------------------------------------------------------------


@dataclass
class Profile:
    """Всё, что бот помнит об игроке. Хранится в fluxus_data.json."""

    name: str = ""
    first_seen: float = 0.0
    last_seen: float = 0.0
    last_visit_at: float = 0.0
    visits: int = 0
    msgs: int = 0
    xp: int = 0
    sparks: int = START_SPARKS
    streak: int = 0
    last_daily: str = ""
    last_xp_at: float = 0.0
    played: int = 0
    wins: int = 0
    quiz_wins: int = 0
    gold_tipped: int = 0
    title: str = ""
    owned: list[str] = field(default_factory=list[str])

    @property
    def level(self) -> int:
        return int((1 + math.sqrt(1 + 4 * self.xp / 25)) / 2)

    @property
    def xp_next(self) -> int:
        """Сколько всего опыта нужно для следующего уровня."""
        return 25 * self.level * (self.level + 1)

    @property
    def shown_title(self) -> str:
        if self.title in SHOP:
            return SHOP[self.title][0]
        return level_title(self.level)

    def to_json(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], asdict(self))

    @classmethod
    def from_json(cls, raw: object) -> Profile:
        profile = cls()
        if not isinstance(raw, dict):
            return profile
        data = cast(dict[str, object], raw)
        for item in fields(cls):
            value = data.get(item.name)
            current = cast(object, getattr(profile, item.name))
            if isinstance(current, str) and isinstance(value, str):
                setattr(profile, item.name, value)
            elif isinstance(current, float) and isinstance(value, (int, float)) and not isinstance(value, bool):
                setattr(profile, item.name, float(value))
            elif isinstance(current, int) and isinstance(value, int) and not isinstance(value, bool):
                setattr(profile, item.name, value)
            elif isinstance(current, list) and isinstance(value, list):
                setattr(profile, item.name, [str(entry) for entry in cast(list[object], value)])
        return profile


@dataclass
class Letter:
    sender: str
    text: str
    at: float

    def to_json(self) -> dict[str, JsonValue]:
        return {"sender": self.sender, "text": self.text, "at": self.at}

    @classmethod
    def from_json(cls, raw: object) -> Letter | None:
        if not isinstance(raw, dict):
            return None
        data = cast(dict[str, object], raw)
        sender, text, at = data.get("sender"), data.get("text"), data.get("at")
        if isinstance(sender, str) and isinstance(text, str) and isinstance(at, (int, float)):
            return cls(sender, text, float(at))
        return None


@dataclass
class Duel:
    challenger_id: str
    challenger: str
    target_id: str
    target: str
    stake: int
    expires: float


@dataclass
class QuizRound:
    question: str
    answers: tuple[str, ...]
    reward: int
    started: float
    ident: int


@dataclass
class GuessRound:
    number: int
    started: float
    guesses: int = 0
    last_guess_at: dict[str, float] = field(default_factory=dict[str, float])


# --------------------------------------------------------------------------------------
# Бот
# --------------------------------------------------------------------------------------


class FluxusBot(Bot):
    """Ведущий комнаты. Подробности - в описании файла."""

    def __init__(self, path: str | Path = DATA_FILE) -> None:
        super().__init__()  # обязательно: иначе команды и таймеры не найдутся
        self.store = JsonStore(path)
        self.rng = random.Random()
        self.profiles: dict[str, Profile] = {}
        self.mail: dict[str, list[Letter]] = {}
        self.rules_text = DEFAULT_RULES
        self._loaded = False
        self._dirty = False
        self._jobs: set[asyncio.Task[None]] = set()
        self._started = time.monotonic()
        self._announced = False
        self._duels: dict[str, Duel] = {}
        self._quiz: QuizRound | None = None
        self._quiz_seq = 0
        self._quiz_recent: list[int] = []
        self._guess: GuessRound | None = None
        self._follow_id: str | None = None
        self._follow_seen: tuple[float, float] | None = None
        self._party: asyncio.Task[None] | None = None
        # Что сервер разрешает боту в этой комнате. Бот узнаёт это из отказов (см. attempt):
        # в 3D-мире нет реакций и посадки, а эмоции там есть только на новых серверах.
        self.can_emote = True
        self.can_react = True
        self.can_sit = True
        self.verify_moves = True  # проверять, что бот и вправду пошёл (в тестах отключается)
        self._dancing = False
        self._last_chat = time.monotonic()
        self._last_ambient = time.monotonic()
        self._last_mention = 0.0
        self._ambient_index = 0
        self._cool: dict[str, float] = {}

    # ---- служебное -------------------------------------------------------------------

    @property
    def me_id(self) -> str:
        return "" if self.session is None else self.session.user_id

    def spawn(self, work: Awaitable[None]) -> None:
        """Фоновая задача: ссылка хранится, ошибки уходят в on_error."""
        task = asyncio.create_task(self._guarded(work))
        self._jobs.add(task)
        task.add_done_callback(self._jobs.discard)

    async def _guarded(self, work: Awaitable[None]) -> None:
        try:
            await work
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self.on_error(error, None)

    async def say(self, text: str) -> None:
        """Сказать в чат; отказ сервера (например, бота заглушили) не валит задачу."""
        try:
            await self.api.chat(text)
        except ResponseError as error:
            logging.getLogger("fluxus").warning("не удалось сказать: %s", error.message)

    async def attempt(self, action: Awaitable[None]) -> bool:
        """Выполнить телодвижение; True - получилось. Отказ сервера - не ошибка бота.

        Если сервер отвечает, что эмоции, реакции или посадка недоступны в 3D, бот это
        запоминает и больше не просит у сервера того же.
        """
        try:
            await action
        except ResponseError as error:
            if "3D" in error.message:
                refused = error.message.casefold()
                if refused.startswith("emote"):
                    self.can_emote = False
                elif refused.startswith("reaction"):
                    self.can_react = False
                elif refused.startswith("sitting"):
                    self.can_sit = False
            return False
        return True

    @property
    def three_d(self) -> bool:
        """Бот в 3D-мире: сервер не принимает там реакции и посадку."""
        return not self.can_react or not self.can_sit

    async def react_to(self, reaction: Reaction, user_id: str) -> bool:
        """Реакция человеку (только 2D-комнаты). В 3D ничего не делает и не пристаёт к серверу."""
        if not self.can_react:
            return False
        return await self.attempt(self.api.react(reaction, user_id))

    def cooled(self, key: str, seconds: float) -> bool:
        """True, если действие можно делать (и запоминает момент), иначе False."""
        now = time.monotonic()
        if now - self._cool.get(key, -1e9) < seconds:
            return False
        self._cool[key] = now
        if len(self._cool) > 2000:
            self._cool = {k: v for k, v in self._cool.items() if now - v < 600}
        return True

    def humans(self) -> list[RoomUser]:
        return [entry for entry in self.room.users() if entry.user.id != self.me_id]

    def profile(self, user_id: str, name: str = "") -> Profile:
        profile = self.profiles.get(user_id)
        if profile is None:
            profile = Profile(name=name, first_seen=time.time())
            self.profiles[user_id] = profile
            self._dirty = True
        if name and profile.name != name:
            profile.name = name
            self._dirty = True
        return profile

    def find_profile(self, name: str) -> tuple[str, Profile] | None:
        wanted = name.lstrip("@").casefold()
        for user_id, profile in self.profiles.items():
            if profile.name.casefold() == wanted:
                return user_id, profile
        return None

    def target(self, name: str | None) -> RoomUser | None:
        """Человек из комнаты по имени (с @ или без)."""
        if not name:
            return None
        entry = self.room.find(name)
        if entry is None or entry.user.id == self.me_id:
            return None
        return entry

    # ---- хранение --------------------------------------------------------------------

    async def _load(self) -> None:
        if self._loaded:
            return
        raw = await self.store.get("db")
        if isinstance(raw, dict):
            db = cast(dict[str, object], raw)
            users = db.get("users")
            if isinstance(users, dict):
                for user_id, data in cast(dict[str, object], users).items():
                    self.profiles[user_id] = Profile.from_json(data)
            mail = db.get("mail")
            if isinstance(mail, dict):
                for user_id, items in cast(dict[str, object], mail).items():
                    if isinstance(items, list):
                        letters = [Letter.from_json(item) for item in cast(list[object], items)]
                        self.mail[user_id] = [letter for letter in letters if letter is not None]
            cfg = db.get("cfg")
            if isinstance(cfg, dict):
                rules = cast(dict[str, object], cfg).get("rules")
                if isinstance(rules, str) and rules.strip():
                    self.rules_text = rules
        self._loaded = True

    def _snapshot(self) -> dict[str, JsonValue]:
        users: dict[str, JsonValue] = {uid: profile.to_json() for uid, profile in self.profiles.items()}
        mail: dict[str, JsonValue] = {
            uid: [letter.to_json() for letter in letters] for uid, letters in self.mail.items() if letters
        }
        cfg: dict[str, JsonValue] = {"rules": self.rules_text}
        return {"users": users, "mail": mail, "cfg": cfg}

    async def save(self) -> None:
        """Записать данные. Снимок делается здесь, пока никто не меняет словари."""
        snapshot = self._snapshot()
        self._dirty = False
        await self.store.set("db", snapshot)

    async def run(
        self,
        *,
        token: str | None = None,
        room_id: str | None = None,
        url: str | None = None,
        clean_room: bool = False,
        reconnect: bool = True,
    ) -> None:
        try:
            await super().run(token=token, room_id=room_id, url=url, clean_room=clean_room, reconnect=reconnect)
        finally:
            for task in list(self._jobs):
                task.cancel()
            if self._loaded:
                await self.save()

    # ---- начисления -------------------------------------------------------------------

    async def gain(self, profile: Profile, xp: int = 0, coins: int = 0) -> int:
        """Начислить опыт и искры; при новом уровне объявить об этом. Возвращает уровень."""
        before = profile.level
        profile.xp += xp
        profile.sparks += coins
        self._dirty = True
        after = profile.level
        if after > before:
            bonus = after * 10
            profile.sparks += bonus
            await self.say(
                f"{profile.name} достигает уровня {after} - {level_title(after)}! "
                f"Награда: {sparks(bonus)}."
            )
        return after

    def parse_stake(self, profile: Profile, args: tuple[str, ...]) -> tuple[int, str | None]:
        """Ставка из аргументов: (искр, ошибка). Без числа ставка нулевая - игра «на интерес»."""
        for raw in args:
            low = raw.casefold()
            if low in ("all", "все", "всё", "allin"):
                return min(profile.sparks, MAX_STAKE), None
            if raw.isdigit():
                stake = int(raw)
                if stake > MAX_STAKE:
                    return 0, f"Максимальная ставка - {sparks(MAX_STAKE)}."
                if stake > profile.sparks:
                    return 0, f"У вас только {sparks(profile.sparks)}."
                return stake, None
        return 0, None

    async def settle(self, profile: Profile, delta: int, won: bool | None) -> None:
        """Итог игры: изменить искры, записать результат и немного опыта."""
        profile.played += 1
        if won:
            profile.wins += 1
        await self.gain(profile, xp=3 if won else 1, coins=delta)

    # ---- события -------------------------------------------------------------------------

    async def on_start(self, session: SessionMetadata) -> None:
        await self._load()
        self._last_chat = time.monotonic()
        # Одна строка в журнале: по ней видно, что бот вошёл, и в какую комнату.
        logging.getLogger("fluxus").info(
            "на связи в комнате «%s» (подключение %s), профилей: %d",
            session.room_info.room_name,
            session.connection_id,
            len(self.profiles),
        )
        # Машем рукой (в 2D и в новом 3D это приветствие) и пробуем сесть на несуществующее
        # место: в 3D сервер отвечает, что посадки там нет, и так бот узнаёт, где он.
        await self.attempt(self.api.emote(WAVE))
        await self.attempt(self.api.sit_on(AnchorPosition("fluxus-probe", 0)))
        if not self._announced:
            self._announced = True
            await self.say(f"{BOT_NAME} на связи! Что я умею - !help. Играем, танцуем, общаемся.")

    async def on_user_join(self, user: User, position: Location) -> None:
        if user.id == self.me_id:
            return
        profile = self.profile(user.id, user.username)
        now = time.time()
        returning = profile.visits > 0
        new_visit = now - profile.last_visit_at > VISIT_GAP
        profile.last_seen = now
        if new_visit:
            profile.visits += 1
            profile.last_visit_at = now
            await self.gain(profile, xp=10)
            if self.is_owner(user):
                line = self.rng.choice(OWNER_GREETINGS)
            elif returning:
                line = self.rng.choice(BACK_GREETINGS)
            else:
                line = self.rng.choice(NEW_GREETINGS)
            await self.say(line.format(name=f"@{user.username}", title=profile.shown_title, visit=profile.visits, bot=BOT_NAME))
            await self.react_to("wave", user.id)
            if profile.last_daily != moscow_day() and returning:
                await self.attempt(self.api.whisper(user.id, "Бонус дня ещё не получен: напишите !daily."))
        letters = self.mail.get(user.id, [])
        if letters:
            await self.attempt(
                self.api.whisper(user.id, f"Вам {plural(len(letters), ('письмо', 'письма', 'писем'))}: прочитайте командой !inbox.")
            )

    async def on_user_leave(self, user: User) -> None:
        if user.id in self.profiles:
            self.profiles[user.id].last_seen = time.time()
            self._dirty = True
        if self._follow_id == user.id:
            self._follow_id = None
            self._follow_seen = None
        for target_id in [tid for tid, duel in self._duels.items() if user.id in (duel.challenger_id, duel.target_id)]:
            del self._duels[target_id]

    async def on_chat(self, user: User, message: str) -> None:
        if user.id == self.me_id:
            return
        self._last_chat = time.monotonic()
        profile = self.profile(user.id, user.username)
        profile.msgs += 1
        text = message.strip()
        if text.startswith("!"):
            return
        now = time.time()
        if now - profile.last_xp_at >= XP_COOLDOWN:
            profile.last_xp_at = now
            await self.gain(profile, xp=2, coins=1)
        await self._check_quiz(user, profile, text)
        await self._check_guess(user, profile, text)
        if re.search(r"\b(fluxus_bot|fluxus|флюкс|флаксус)\b", text.casefold()) and self.cooled("mention", 20.0):
            await self.say(self.rng.choice(MENTION_REPLIES).format(name=f"@{user.username}"))

    async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None:
        """Эмоция, направленная на бота: отвечаем реакцией и иногда словом."""
        if receiver is None or receiver.id != self.me_id or user.id == self.me_id:
            return
        if not self.cooled(f"emote:{user.id}", 15.0):
            return
        await self.react_to(self.rng.choice(REACTIONS), user.id)
        if self.rng.random() < 0.5:
            await self.say(f"@{user.username}, я это заметил и тронут.")

    async def on_reaction(self, user: User, reaction: str, receiver: User) -> None:
        if receiver.id != self.me_id or user.id == self.me_id:
            return
        if not self.cooled(f"reaction:{user.id}", 15.0):
            return
        await self.react_to("heart", user.id)
        if reaction == "heart":
            await self.say(f"Спасибо, @{user.username}! Взаимно.")

    async def on_tip(self, sender: User, receiver: User, item: Item | CurrencyItem) -> None:
        """Чаевые боту (золото). Событие приходит и о чужих чаевых в комнате - их пропускаем."""
        if receiver.id != self.me_id or sender.id == self.me_id or not isinstance(item, CurrencyItem):
            return
        amount = item.amount
        if amount <= 0:
            return
        profile = self.profile(sender.id, sender.username)
        profile.gold_tipped += amount
        reward = amount * GOLD_TO_SPARKS
        await self.gain(profile, xp=amount, coins=reward)
        await self.save()
        big = amount >= 50
        await self.say(
            f"Спасибо, @{sender.username}! {amount} золота принято, вам {sparks(reward)}."
            + (" Это щедро, ради вас станцую!" if big else "")
        )
        await self.react_to("heart", sender.id)
        if big and (self._party is None or self._party.done()):
            self.spawn(self._celebrate())

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        """Личное сообщение: отвечаем на несколько простых слов."""
        if user_id == self.me_id:
            return
        messages = await self.api.messages(conversation_id)
        if not messages or messages[0].sender_id != user_id:
            return
        answer = await self.dm_answer(user_id, messages[0].content, is_new_conversation)
        await self.api.send_message(conversation_id, answer)

    # ---- викторина и угадай-число (проверка ответов) -----------------------------------

    async def _check_quiz(self, user: User, profile: Profile, text: str) -> None:
        quiz = self._quiz
        if quiz is None or not any(contains_phrase(text, answer) for answer in quiz.answers):
            return
        self._quiz = None
        elapsed = time.monotonic() - quiz.started
        reward = quiz.reward + (10 if elapsed < 10 else 0)
        profile.quiz_wins += 1
        profile.played += 1
        profile.wins += 1
        await self.gain(profile, xp=15, coins=reward)
        await self.save()
        await self.say(
            f"Верно, @{user.username}! Ответ: {quiz.answers[0]}. "
            f"Награда: {sparks(reward)}" + (" (с бонусом за скорость)." if elapsed < 10 else ".")
        )

    async def _check_guess(self, user: User, profile: Profile, text: str) -> None:
        game = self._guess
        if game is None or not text.isdigit() or len(text) > 3:
            return
        now = time.monotonic()
        if now - game.last_guess_at.get(user.id, -1e9) < 2.0:
            return
        game.last_guess_at[user.id] = now
        guess = int(text)
        if not 1 <= guess <= 100:
            return
        game.guesses += 1
        if guess == game.number:
            self._guess = None
            reward = max(20, 100 - game.guesses * 5)
            profile.played += 1
            profile.wins += 1
            await self.gain(profile, xp=10, coins=reward)
            await self.save()
            await self.say(
                f"@{user.username} угадал(а) число {game.number} с попытки номер {game.guesses}! "
                f"Награда: {sparks(reward)}."
            )
        else:
            await self.say(f"@{user.username}: {'больше' if guess < game.number else 'меньше'} чем {guess}.")

    # ---- таймеры -------------------------------------------------------------------------

    @every(15)
    async def autosave(self) -> None:
        if self._dirty and self._loaded:
            await self.save()

    @every(4)
    async def follow_tick(self) -> None:
        """Если бот идёт за человеком, подтянуть его к тому, когда тот сдвинулся."""
        if self._follow_id is None:
            return
        where = await self.where(self._follow_id)
        if where is None:
            self._follow_id = None
            return
        if isinstance(where, Position):
            here = (where.x, where.z)
            seen = self._follow_seen
            if seen is None or math.hypot(here[0] - seen[0], here[1] - seen[1]) > 1.5:
                self._follow_seen = here
                await self.walk_near(where)

    @every(35)
    async def wander(self) -> None:
        """Когда никто не командует, бот живёт своей жизнью: ходит и жестикулирует."""
        busy = self._follow_id is not None or (self._party is not None and not self._party.done())
        people = self.humans()
        if busy or not people or self.rng.random() > 0.5:
            return
        if self.rng.random() < 0.5:
            entry = self.rng.choice(people)
            where = await self.where(entry.user.id)
            if isinstance(where, Position):
                await self.walk_near(where)
        elif not self.can_emote:
            here = await self.where(self.me_id)
            if isinstance(here, Position):
                self.spawn(self.walk_dance(self.rng.choice(("circle", "zigzag", "square")), here))
        else:
            emote_id, _ = self.rng.choice(GESTURES)
            await self.attempt(self.api.emote(emote_id))

    @every(60)
    async def ambient(self) -> None:
        """Раз в десять минут, если в комнате тихо, подсказать, что тут можно делать."""
        now = time.monotonic()
        if not self.humans() or now - self._last_chat < 150 or now - self._last_ambient < 600:
            return
        if self._quiz is not None or self._guess is not None:
            return
        self._last_ambient = now
        line = AMBIENT[self._ambient_index % len(AMBIENT)]
        self._ambient_index += 1
        await self.say(line.format(bot=BOT_NAME, fact=self.rng.choice(FACTS)))

    # ---- движение ------------------------------------------------------------------------

    async def where(self, user_id: str) -> Location | None:
        for entry in await self.api.list_room_users():
            if entry.user.id == user_id:
                return entry.location
        return None

    async def walk_near(self, spot: Position) -> bool:
        """Подойти к человеку. True - бот и вправду пошёл (или уже рядом).

        Сервер 3D-мира ничего не отвечает на недостижимую точку (за мебелью, вне пола):
        бот просто остаётся стоять. Поэтому после каждой попытки смотрим, сдвинулся ли
        он, и если нет - пробуем следующую точку рядом с человеком.
        """
        start = await self.where(self.me_id)
        if isinstance(start, Position) and math.hypot(start.x - spot.x, start.z - spot.z) <= CLOSE_ENOUGH:
            return True  # уже рядом
        for dx, dz in APPROACH:
            goal = Position(spot.x + dx, spot.y, spot.z + dz, facing="FrontLeft")
            before = await self.where(self.me_id)
            if isinstance(before, Position) and math.hypot(before.x - goal.x, before.z - goal.z) < 0.6:
                return True
            if not await self.attempt(self.api.move_to(goal)):
                continue
            if not self.verify_moves:
                return True
            await asyncio.sleep(MOVE_CHECK)
            after = await self.where(self.me_id)
            if isinstance(after, Position) and isinstance(before, Position):
                moved = math.hypot(after.x - before.x, after.z - before.z)
                if moved > 0.2 or math.hypot(after.x - goal.x, after.z - goal.z) < 0.6:
                    return True
        return False

    async def sit_near(self, seat: AnchorPosition) -> bool:
        if not self.can_sit:
            return False
        for step in (1, -1, 2, -2):
            if await self.attempt(self.api.sit_on(AnchorPosition(seat.entity_id, seat.anchor_ix + step))):
                return True
        return False

    async def dance_now(self, emote_id: str) -> bool:
        """Сыграть эмоцию, если сервер разрешает их боту в этой комнате."""
        if not self.can_emote:
            return False
        return await self.attempt(self.api.emote(emote_id))

    async def walk_dance(self, style: str, center: Position) -> None:
        """Станцевать ходьбой: пройти фигуру вокруг центра. Два танца сразу не идут."""
        if self._dancing:
            return
        self._dancing = True
        try:
            for step in dance_path(style, center):
                if not await self.attempt(self.api.move_to(step)):
                    return
                await asyncio.sleep(STEP_PAUSE)
        finally:
            self._dancing = False

    async def _celebrate(self) -> None:
        await self.dance_now("emote-celebrate")
        for entry in self.rng.sample(self.humans(), k=min(3, len(self.humans()))):
            await self.react_to(self.rng.choice(REACTIONS), entry.user.id)
            await asyncio.sleep(1.0)

    async def _party_show(self, starter: str) -> None:
        await self.say(f"Вечеринка от {starter}! Держитесь крепче.")
        for _ in range(5):
            if not self.can_emote:
                style = self.rng.choice(sorted(WALK_DANCES))
                here = await self.where(self.me_id)
                if not isinstance(here, Position):
                    break
                await self.say(f"Номер программы: {WALK_DANCES[style]}!")
                await self.walk_dance(style, here)
                continue
            emote_id, _ = DANCES[self.rng.choice(sorted(DANCES))]
            if not await self.dance_now(emote_id):
                continue  # возможно, мы только что узнали, что эмоций тут нет: следующий круг пойдёт ходьбой
            people = self.humans()
            if people:
                await self.react_to(self.rng.choice(REACTIONS), self.rng.choice(people).user.id)
            await asyncio.sleep(7.0)
        await self.say("Спасибо за танцы! Было жарко.")

    # ---- личные сообщения -----------------------------------------------------------------

    async def dm_answer(self, user_id: str, text: str, first: bool) -> str:
        word = normalize(text).split(" ")[0] if normalize(text) else ""
        profile = self.profile(user_id)
        if word in ("помощь", "help", "команды", "привет", "start", "старт") or not word:
            return (
                f"Я {BOT_NAME}, ведущий комнаты. Здесь я понимаю слова: профиль, бонус, топ, правила, почта. "
                "Все остальные команды (игры, танцы, шутки) - в комнате: напишите там !help."
                + (" Рад знакомству!" if first else "")
            )
        if word in ("профиль", "me", "я"):
            return self.profile_text(profile)
        if word in ("бонус", "daily"):
            return await self.daily_text(profile)
        if word in ("топ", "top"):
            return self.top_text("уровень")
        if word in ("правила", "rules"):
            return self.rules_text
        if word in ("почта", "письма", "inbox"):
            return self.inbox_text(user_id)
        return "Не понял. Напишите «помощь», и я расскажу, что умею."

    # ---- тексты общего назначения ----------------------------------------------------------

    def profile_text(self, profile: Profile) -> str:
        name = profile.name or "Игрок"
        wins = f", побед {profile.wins} из {profile.played}" if profile.played else ""
        streak = f", серия бонусов {plural(profile.streak, ('день', 'дня', 'дней'))}" if profile.streak else ""
        return (
            f"{profile.shown_title} {name}: уровень {profile.level} (опыт {profile.xp}/{profile.xp_next}), "
            f"{sparks(profile.sparks)}, визитов {profile.visits}{wins}{streak}."
        )

    async def daily_text(self, profile: Profile) -> str:
        today = moscow_day()
        if profile.last_daily == today:
            return "Бонус на сегодня уже получен. Новые сутки начинаются в полночь по Москве."
        profile.streak = profile.streak + 1 if profile.last_daily == moscow_day(-1) else 1
        profile.last_daily = today
        bonus = DAILY_BASE + DAILY_STEP * min(profile.streak - 1, DAILY_STEP_CAP)
        await self.gain(profile, xp=25, coins=bonus)
        await self.save()
        return (
            f"Бонус дня: {sparks(bonus)}! Серия: {plural(profile.streak, ('день', 'дня', 'дней'))} подряд. "
            "Заходите каждый день: за серию награда растёт."
        )

    def top_text(self, kind: str) -> str:
        kind = kind.casefold()
        if kind in ("искры", "sparks", "iskry"):
            title, rows = "по искрам", [(p.sparks, p.name) for p in self.profiles.values()]
        elif kind in ("викторина", "quiz"):
            title, rows = "по викторине", [(p.quiz_wins, p.name) for p in self.profiles.values()]
        elif kind in ("щедрые", "tips", "donors", "золото"):
            title, rows = "самых щедрых (золото)", [(p.gold_tipped, p.name) for p in self.profiles.values()]
        else:
            title, rows = "по уровню", [(p.xp, f"{p.name} ({p.level})") for p in self.profiles.values()]
        rows = sorted((row for row in rows if row[0] > 0 and row[1]), reverse=True)[:5]
        if not rows:
            return f"Топ {title}: пока пусто."
        return f"Топ {title}: " + " | ".join(f"{i}. {name} - {value}" for i, (value, name) in enumerate(rows, 1))

    def inbox_text(self, user_id: str) -> str:
        letters = self.mail.pop(user_id, [])
        if not letters:
            return "Писем нет."
        self._dirty = True
        return "Ваши письма: " + " || ".join(f"от {letter.sender} ({ago(time.time() - letter.at)}): {letter.text}" for letter in letters)

    # ======================================================================================
    # Команды
    # ======================================================================================

    @command("help", aliases=("помощь", "команды", "?"), cooldown=(6, 30.0), description="что я умею")
    async def help_command(self, ctx: Context) -> None:
        topic = normalize(ctx.rest())
        topic = HELP_ALIASES.get(topic, topic)
        text = HELP_TOPICS.get(topic)
        if text is None:
            await ctx.reply(HELP_OVERVIEW.format(bot=BOT_NAME))
        else:
            await ctx.reply(text.format(stake=MAX_STAKE))

    # ---- профиль ------------------------------------------------------------------------

    @command("me", aliases=("профиль", "я"), cooldown=(4, 30.0), description="профиль: !me [имя]")
    async def me(self, ctx: Context) -> None:
        name = ctx.arg(0)
        if name is None:
            await ctx.reply(self.profile_text(self.profile(ctx.user.id, ctx.user.username)))
            return
        found = self.find_profile(name)
        await ctx.reply(self.profile_text(found[1]) if found else f"Я не знаю игрока «{name.lstrip('@')}».")

    @command("daily", aliases=("бонус", "ежедневно"), cooldown=(3, 30.0), description="бонус дня")
    async def daily(self, ctx: Context) -> None:
        await ctx.reply(f"@{ctx.user.username}: " + await self.daily_text(self.profile(ctx.user.id, ctx.user.username)))

    @command("top", aliases=("топ", "лидеры"), cooldown=(3, 30.0), description="топ: !top искры|уровень|викторина|щедрые")
    async def top(self, ctx: Context) -> None:
        await ctx.reply(self.top_text(ctx.arg(0) or "уровень"))

    @command("shop", aliases=("магазин",), cooldown=(3, 30.0), description="магазин титулов")
    async def shop(self, ctx: Context) -> None:
        items = " | ".join(f"{name} - {sparks(price)}" for name, price in SHOP.values())
        await ctx.reply(f"Титулы: {items}. Купить: !buy название. Надеть: !title название.")

    @command("buy", aliases=("купить",), cooldown=(3, 20.0), description="купить титул: !buy название")
    async def buy(self, ctx: Context) -> None:
        key = self._shop_key(ctx.arg(0))
        profile = self.profile(ctx.user.id, ctx.user.username)
        if key is None:
            await ctx.reply("Такого титула нет. Список: !shop")
        elif key in profile.owned:
            await ctx.reply("Этот титул у вас уже есть. Надеть: !title " + SHOP[key][0])
        elif profile.sparks < SHOP[key][1]:
            await ctx.reply(f"Не хватает искр: нужно {SHOP[key][1]}, у вас {profile.sparks}.")
        else:
            profile.sparks -= SHOP[key][1]
            profile.owned.append(key)
            profile.title = key
            self._dirty = True
            await self.save()
            await ctx.reply(f"Поздравляю, @{ctx.user.username}! Вы теперь «{SHOP[key][0]}».")

    @command("title", aliases=("титул",), cooldown=(3, 20.0), description="сменить титул: !title название или off")
    async def title(self, ctx: Context) -> None:
        profile = self.profile(ctx.user.id, ctx.user.username)
        arg = (ctx.arg(0) or "").casefold()
        if arg in ("off", "нет", "снять"):
            profile.title = ""
            self._dirty = True
            await ctx.reply(f"Теперь вы «{profile.shown_title}».")
            return
        key = self._shop_key(arg)
        if key is None or key not in profile.owned:
            owned = ", ".join(SHOP[k][0] for k in profile.owned) or "пока нет"
            await ctx.reply(f"Доступные вам титулы: {owned}. Купить новые: !shop")
            return
        profile.title = key
        self._dirty = True
        await ctx.reply(f"Теперь вы «{SHOP[key][0]}».")

    @staticmethod
    def _shop_key(name: str | None) -> str | None:
        if not name:
            return None
        low = name.casefold()
        if low in SHOP:
            return low
        return SHOP_ALIASES.get(low)

    # ---- игры ---------------------------------------------------------------------------

    @command("dice", aliases=("кубик", "кости"), cooldown=(4, 30.0), description="кубики против меня: !dice [ставка]")
    async def dice(self, ctx: Context) -> None:
        profile = self.profile(ctx.user.id, ctx.user.username)
        stake, error = self.parse_stake(profile, ctx.args)
        if error:
            await ctx.reply(error)
            return
        mine = (self.rng.randint(1, 6), self.rng.randint(1, 6))
        theirs = (self.rng.randint(1, 6), self.rng.randint(1, 6))
        a, b = sum(mine), sum(theirs)
        line = f"@{ctx.user.username}: {mine[0]}+{mine[1]}={a}, у меня {theirs[0]}+{theirs[1]}={b}. "
        if a > b:
            await self.settle(profile, stake, True)
            await ctx.reply(line + "Ваша победа!" + (f" +{sparks(stake)}." if stake else ""))
        elif a < b:
            await self.settle(profile, -stake, False)
            await ctx.reply(line + "Победа за мной." + (f" -{sparks(stake)}." if stake else ""))
        else:
            await self.settle(profile, 0, None)
            await ctx.reply(line + "Ничья, ставка возвращается.")

    @command("coin", aliases=("монета", "монетка"), cooldown=(4, 30.0), description="орёл или решка: !coin орёл [ставка]")
    async def coin(self, ctx: Context) -> None:
        profile = self.profile(ctx.user.id, ctx.user.username)
        stake, error = self.parse_stake(profile, ctx.args)
        if error:
            await ctx.reply(error)
            return
        sides = {"орел": "орёл", "орёл": "орёл", "heads": "орёл", "o": "орёл", "решка": "решка", "tails": "решка", "р": "решка", "r": "решка"}
        guess = next((sides[a.casefold()] for a in ctx.args if a.casefold() in sides), None)
        if guess is None:
            await ctx.reply("Выберите сторону: !coin орёл или !coin решка (и ставка, если хотите).")
            return
        flip = self.rng.choice(("орёл", "решка"))
        won = flip == guess
        await self.settle(profile, stake if won else -stake, won)
        tail = (f" +{sparks(stake)}." if won else f" -{sparks(stake)}.") if stake else ""
        await ctx.reply(f"@{ctx.user.username}: выпал {flip} - {'угадали' if won else 'не повезло'}.{tail}")

    @command("slots", aliases=("слоты", "автомат"), cooldown=(4, 30.0), description="игровой автомат: !slots [ставка]")
    async def slots(self, ctx: Context) -> None:
        profile = self.profile(ctx.user.id, ctx.user.username)
        stake, error = self.parse_stake(profile, ctx.args)
        if error:
            await ctx.reply(error)
            return
        names = [name for name, _ in SLOT_REELS]
        weights = [weight for _, weight in SLOT_REELS]
        reels = self.rng.choices(names, weights=weights, k=3)
        shown = "[" + "] [".join(reels) + "]"
        if len(set(reels)) == 1:
            payout = stake * SLOT_JACKPOT[reels[0]]
            await self.settle(profile, payout - stake, True)
            await ctx.reply(f"@{ctx.user.username}: {shown} - ДЖЕКПОТ!" + (f" +{sparks(payout - stake)}." if stake else ""))
        elif len(set(reels)) == 2:
            await self.settle(profile, 0, None)
            await ctx.reply(f"@{ctx.user.username}: {shown} - пара, ставка возвращается.")
        else:
            await self.settle(profile, -stake, False)
            await ctx.reply(f"@{ctx.user.username}: {shown} - не в этот раз." + (f" -{sparks(stake)}." if stake else ""))

    @command("rps", aliases=("кмн", "камень"), cooldown=(4, 30.0), description="камень-ножницы-бумага: !rps камень [ставка]")
    async def rps(self, ctx: Context) -> None:
        profile = self.profile(ctx.user.id, ctx.user.username)
        stake, error = self.parse_stake(profile, ctx.args)
        if error:
            await ctx.reply(error)
            return
        names = {"камень": "камень", "к": "камень", "rock": "камень", "ножницы": "ножницы", "н": "ножницы", "scissors": "ножницы", "бумага": "бумага", "б": "бумага", "paper": "бумага"}
        pick = next((names[a.casefold()] for a in ctx.args if a.casefold() in names), None)
        if pick is None:
            await ctx.reply("Выберите: !rps камень, !rps ножницы или !rps бумага (и ставка).")
            return
        mine = self.rng.choice(("камень", "ножницы", "бумага"))
        beats = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}
        line = f"@{ctx.user.username}: у вас {pick}, у меня {mine}. "
        if pick == mine:
            await self.settle(profile, 0, None)
            await ctx.reply(line + "Ничья.")
        elif beats[pick] == mine:
            await self.settle(profile, stake, True)
            await ctx.reply(line + "Вы выиграли!" + (f" +{sparks(stake)}." if stake else ""))
        else:
            await self.settle(profile, -stake, False)
            await ctx.reply(line + "Выиграл я." + (f" -{sparks(stake)}." if stake else ""))

    @command("duel", aliases=("дуэль",), cooldown=(3, 60.0), description="вызвать на дуэль: !duel имя [ставка]")
    async def duel(self, ctx: Context) -> None:
        entry = self.target(ctx.arg(0))
        if entry is None or entry.user.id == ctx.user.id:
            await ctx.reply("Укажите соперника из комнаты: !duel имя [ставка]. С собой драться нельзя.")
            return
        profile = self.profile(ctx.user.id, ctx.user.username)
        stake, error = self.parse_stake(profile, ctx.args[1:])
        if error:
            await ctx.reply(error)
            return
        self._duels[entry.user.id] = Duel(ctx.user.id, ctx.user.username, entry.user.id, entry.user.username, stake, time.monotonic() + DUEL_TTL)
        bet = f"Ставка: {sparks(stake)}." if stake else "Ставки нет - дуэль на честь."
        await ctx.reply(f"@{ctx.user.username} вызывает @{entry.user.username} на дуэль! {bet} @{entry.user.username}, ответьте !accept или !decline в течение минуты.")

    @command("accept", aliases=("принять",), cooldown=(3, 20.0), description="принять дуэль")
    async def accept(self, ctx: Context) -> None:
        duel = self._duels.pop(ctx.user.id, None)
        if duel is None or duel.expires < time.monotonic():
            await ctx.reply("Вас никто не вызывал, или вызов уже истёк.")
            return
        challenger = self.profile(duel.challenger_id, duel.challenger)
        defender = self.profile(ctx.user.id, ctx.user.username)
        if duel.challenger_id not in self.room:
            await ctx.reply(f"{duel.challenger} уже ушёл из комнаты. Дуэль отменена.")
            return
        if duel.stake > min(challenger.sparks, defender.sparks):
            await ctx.reply("У кого-то из дуэлянтов не хватает искр на ставку. Дуэль отменена.")
            return
        self.spawn(self._run_duel(duel, challenger, defender))

    @command("decline", aliases=("отказ", "отклонить"), cooldown=(3, 20.0), description="отклонить дуэль")
    async def decline(self, ctx: Context) -> None:
        duel = self._duels.pop(ctx.user.id, None)
        await ctx.reply(f"@{duel.challenger}, {ctx.user.username} отказывается от дуэли." if duel else "Вас никто не вызывал.")

    async def _run_duel(self, duel: Duel, challenger: Profile, defender: Profile) -> None:
        await self.say(f"Дуэль: @{duel.challenger} против @{duel.target}! Дуэлянты расходятся...")
        await asyncio.sleep(2.0)
        await self.say("Три... два... один...")
        await asyncio.sleep(2.0)
        challenger_wins = self.rng.random() < 0.5
        winner, loser = (challenger, defender) if challenger_wins else (defender, challenger)
        winner_name, loser_name = (duel.challenger, duel.target) if challenger_wins else (duel.target, duel.challenger)
        await self.settle(winner, duel.stake, True)
        await self.settle(loser, -duel.stake, False)
        await self.save()
        prize = f" Забирает {sparks(duel.stake)}." if duel.stake else ""
        await self.say(f"Победил @{winner_name}!{prize} @{loser_name}, не огорчайтесь: реванш за вами.")

    @command("quiz", aliases=("викторина", "вопрос"), cooldown=(2, 60.0), description="викторина на всю комнату")
    async def quiz(self, ctx: Context) -> None:
        if self._quiz is not None:
            await ctx.reply(f"Вопрос ещё открыт: {self._quiz.question}")
            return
        if self._guess is not None:
            await ctx.reply("Сейчас идёт игра «угадай число». Дождитесь её конца.")
            return
        choices = [i for i in range(len(QUIZ)) if i not in self._quiz_recent] or list(range(len(QUIZ)))
        index = self.rng.choice(choices)
        self._quiz_recent = (self._quiz_recent + [index])[-12:]
        question, answers = QUIZ[index]
        self._quiz_seq += 1
        self._quiz = QuizRound(question, answers, 30, time.monotonic(), self._quiz_seq)
        await ctx.reply(f"ВИКТОРИНА (награда {sparks(30)}, +10 за скорость). {question} Отвечайте прямо в чат!")
        self.spawn(self._quiz_clock(self._quiz))

    def _quiz_is(self, quiz: QuizRound) -> bool:
        """Тот же ли это раунд, что идёт сейчас (после ожидания мог начаться другой)."""
        return self._quiz is not None and self._quiz.ident == quiz.ident

    async def _quiz_clock(self, quiz: QuizRound) -> None:
        await asyncio.sleep(QUIZ_HINT_AFTER)
        if not self._quiz_is(quiz):
            return
        answer = quiz.answers[0]
        if answer.isdigit():
            hint = f"число из {len(answer)} цифр"
        else:
            hint = f"{plural(len(answer), ('буква', 'буквы', 'букв'))}, первая «{answer[0].upper()}»"
        await self.say(f"Подсказка: {hint}.")
        await asyncio.sleep(QUIZ_TIME - QUIZ_HINT_AFTER)
        if self._quiz_is(quiz):
            self._quiz = None
            await self.say(f"Время вышло! Правильный ответ: {answer}. Следующий вопрос - по команде !quiz.")

    @command("guess", aliases=("угадай", "число"), cooldown=(2, 60.0), description="угадай число от 1 до 100 всей комнатой")
    async def guess(self, ctx: Context) -> None:
        if self._guess is not None:
            await ctx.reply("Игра уже идёт: загадано число от 1 до 100, пишите догадки в чат.")
            return
        if self._quiz is not None:
            await ctx.reply("Сейчас идёт викторина. Дождитесь её конца.")
            return
        game = GuessRound(self.rng.randint(1, 100), time.monotonic())
        self._guess = game
        await ctx.reply("Я загадал число от 1 до 100. Пишите догадки прямо в чат - я скажу «больше» или «меньше». Победитель получит искры!")
        self.spawn(self._guess_clock(game))

    async def _guess_clock(self, game: GuessRound) -> None:
        await asyncio.sleep(GUESS_TIME)
        if self._guess is game:
            self._guess = None
            await self.say(f"Время вышло. Я загадывал число {game.number}.")

    # ---- веселье -------------------------------------------------------------------------

    @command("8ball", aliases=("шар", "предсказание"), cooldown=(3, 20.0), description="шар предсказаний: !8ball вопрос")
    async def eight_ball(self, ctx: Context) -> None:
        if not ctx.rest():
            await ctx.reply("Задайте вопрос: !8ball будет ли у нас весело?")
            return
        await ctx.reply(f"@{ctx.user.username}: {self.rng.choice(BALL_ANSWERS)}")

    @command("roll", aliases=("бросок",), cooldown=(4, 20.0), description="бросить кости: !roll 2d6")
    async def roll(self, ctx: Context) -> None:
        match = re.fullmatch(r"(\d{1,2})?[dд](\d{1,4})", (ctx.arg(0) or "1d6").casefold())
        if match is None:
            await ctx.reply("Формат такой: !roll 2d6 (кубиков до 20, граней до 1000).")
            return
        count, sides = int(match.group(1) or 1), int(match.group(2))
        if not 1 <= count <= 20 or not 2 <= sides <= 1000:
            await ctx.reply("Кубиков от 1 до 20, граней от 2 до 1000.")
            return
        rolls = [self.rng.randint(1, sides) for _ in range(count)]
        detail = f" ({'+'.join(map(str, rolls))})" if count > 1 else ""
        await ctx.reply(f"@{ctx.user.username} бросает {count}d{sides}: {sum(rolls)}{detail}")

    @command("pick", aliases=("выбери",), cooldown=(3, 20.0), description="выбрать из вариантов: !pick чай, кофе, сок")
    async def pick(self, ctx: Context) -> None:
        options = [part.strip() for part in re.split(r"[,;|]|\sили\s", ctx.rest()) if part.strip()]
        if len(options) < 2:
            await ctx.reply("Дайте хотя бы два варианта: !pick чай, кофе")
            return
        await ctx.reply(f"Выбираю: {self.rng.choice(options)}")

    @command("ship", aliases=("пара", "совместимость"), cooldown=(3, 30.0), description="совместимость: !ship имя [имя]")
    async def ship(self, ctx: Context) -> None:
        names = [arg.lstrip("@") for arg in ctx.args[:2]]
        if not names:
            await ctx.reply("Укажите имя: !ship имя или !ship имя1 имя2.")
            return
        pair = (ctx.user.username, names[0]) if len(names) == 1 else (names[0], names[1])
        percent = stable_percent(*pair)
        verdict = "искры летят!" if percent >= 80 else "всё серьёзно." if percent >= 55 else "есть над чем поработать." if percent >= 30 else "лучше остаться друзьями."
        await ctx.reply(f"{pair[0]} + {pair[1]} = {percent}%: {verdict}")

    @command("rate", aliases=("оцени",), cooldown=(3, 20.0), description="оценка чего угодно: !rate пицца")
    async def rate(self, ctx: Context) -> None:
        if not ctx.rest():
            await ctx.reply("Что оценить? !rate пицца")
            return
        await ctx.reply(f"{ctx.rest()}: {stable_percent(ctx.rest()) // 10} из 10.")

    @command("who", aliases=("кто",), cooldown=(3, 30.0), description="выбрать случайного человека: !who самый милый")
    async def who(self, ctx: Context) -> None:
        people = self.humans()
        if not people:
            await ctx.reply("В комнате пусто.")
            return
        chosen = self.rng.choice(people).user.username
        await ctx.reply(f"{ctx.rest() or 'Сегодня везёт'}: @{chosen}")

    @command("joke", aliases=("шутка", "анекдот"), cooldown=(2, 30.0), description="шутка")
    async def joke(self, ctx: Context) -> None:
        await ctx.reply(self.rng.choice(JOKES))

    @command("fact", aliases=("факт",), cooldown=(2, 30.0), description="интересный факт")
    async def fact(self, ctx: Context) -> None:
        await ctx.reply(self.rng.choice(FACTS))

    @command("praise", aliases=("комплимент", "похвали"), cooldown=(3, 30.0), description="комплимент: !praise [имя]")
    async def praise(self, ctx: Context) -> None:
        name = self._name_of(ctx)
        await ctx.reply(self.rng.choice(PRAISES).format(name=f"@{name}"))
        await self._react_to(name)

    @command("roast", aliases=("подколи",), cooldown=(3, 30.0), description="добрая подколка: !roast [имя]")
    async def roast(self, ctx: Context) -> None:
        await ctx.reply(self.rng.choice(ROASTS).format(name=f"@{self._name_of(ctx)}"))

    @command("hug", aliases=("обнять", "обними"), cooldown=(3, 30.0), description="обнять: !hug [имя]")
    async def hug(self, ctx: Context) -> None:
        name = self._name_of(ctx)
        entry = self.room.find(name)
        if entry is not None:  # подойти, как положено перед объятием
            spot = await self.where(entry.user.id)
            if isinstance(spot, Position):
                await self.walk_near(spot)
        await ctx.reply(self.rng.choice(HUGS).format(bot=BOT_NAME, name=f"@{name}"))
        await self._react_to(name)

    def _name_of(self, ctx: Context) -> str:
        entry = self.target(ctx.arg(0))
        return entry.user.username if entry else ctx.user.username

    async def _react_to(self, username: str) -> None:
        entry = self.room.find(username)
        if entry is not None:
            await self.react_to("heart", entry.user.id)

    # ---- тело бота ---------------------------------------------------------------------------

    @command("dance", aliases=("танец", "танцуй"), cooldown=(3, 20.0), description="станцевать: !dance [название]")
    async def dance(self, ctx: Context) -> None:
        wanted = (ctx.arg(0) or "").casefold()
        key = DANCE_ALIASES.get(wanted, wanted)
        style = WALK_ALIASES.get(wanted, wanted)
        if wanted and key not in DANCES and style not in WALK_DANCES:
            await ctx.reply("Такого танца нет. Список: !dances")
            return
        if self.can_emote and (not wanted or key in DANCES):
            emote_id, title = DANCES[key or self.rng.choice(sorted(DANCES))]
            if await self.dance_now(emote_id):
                await ctx.reply(f"Танцую: {title}!")
                return
        if wanted and style not in WALK_DANCES:  # название настоящего танца, а эмоций тут нет
            await ctx.reply("Настоящие танцы в этой комнате мне недоступны, но могу фигурами: !dances")
            return
        here = await self.where(self.me_id)
        if not isinstance(here, Position):
            await ctx.reply("Не вижу, где я стою, поэтому не могу танцевать.")
            return
        style = style if style in WALK_DANCES else self.rng.choice(sorted(WALK_DANCES))
        await ctx.reply(f"Танцую: {WALK_DANCES[style]}! Смотрите под ноги.")
        self.spawn(self.walk_dance(style, here))

    @command("dances", aliases=("танцы",), cooldown=(2, 30.0), description="список танцев")
    async def dances(self, ctx: Context) -> None:
        figures = "Фигурами: " + ", ".join(sorted(WALK_DANCES)) + " (!dance star), вокруг вас: !orbit"
        if self.can_emote:
            await ctx.reply("Танцы: " + ", ".join(sorted(DANCES)) + " (!dance kpop). " + figures)
        else:
            await ctx.reply("Танцую фигурами: " + ", ".join(sorted(WALK_DANCES)) + " (!dance star). Вокруг вас: !orbit")

    @command("orbit", aliases=("орбита", "кружись"), cooldown=(2, 40.0), description="покружить вокруг вас")
    async def orbit(self, ctx: Context) -> None:
        where = await self.where(ctx.user.id)
        if not isinstance(where, Position):
            await ctx.reply("Не вижу вас на полу: встаньте, и я покружу вокруг.")
            return
        await ctx.reply(f"Кружу вокруг @{ctx.user.username}!")
        self.spawn(self.walk_dance("orbit", where))

    @command("party", aliases=("вечеринка", "тусовка"), cooldown=(1, 180.0), description="устроить вечеринку")
    async def party(self, ctx: Context) -> None:
        if self._party is not None and not self._party.done():
            await ctx.reply("Вечеринка уже идёт!")
            return
        self._party = asyncio.create_task(self._guarded(self._party_show(ctx.user.username)))
        self._jobs.add(self._party)
        self._party.add_done_callback(self._jobs.discard)

    @command("come", aliases=("ко-мне", "иди"), cooldown=(3, 20.0), description="подойти к вам")
    async def come(self, ctx: Context) -> None:
        where = await self.where(ctx.user.id)
        if isinstance(where, Position):
            ok = await self.walk_near(where)
            await ctx.reply("Иду к вам!" if ok else "Не получилось дойти: что-то мешает, или туда мне нельзя.")
        elif isinstance(where, AnchorPosition):
            ok = await self.sit_near(where)
            await ctx.reply("Присаживаюсь рядом." if ok else "Вы сидите, а свободного места рядом нет.")
        else:
            await ctx.reply("Не вижу, где вы.")

    @command("follow", aliases=("следуй", "за-мной"), cooldown=(2, 20.0), description="ходить за вами")
    async def follow(self, ctx: Context) -> None:
        where = await self.where(ctx.user.id)
        if not isinstance(where, Position):
            await ctx.reply("Не вижу вас на полу: встаньте, и я пойду за вами.")
            return
        if not await self.walk_near(where):
            await ctx.reply("Не получилось сдвинуться с места: возможно, мне сюда нельзя. Попробуйте встать на открытое место.")
            return
        self._follow_id = ctx.user.id
        self._follow_seen = (where.x, where.z)
        await ctx.reply(f"Иду за вами, @{ctx.user.username}. Остановить: !stay")

    @command("stay", aliases=("стой", "стоп"), cooldown=(2, 10.0), description="остановиться")
    async def stay(self, ctx: Context) -> None:
        self._follow_id = None
        self._follow_seen = None
        if self._party is not None and not self._party.done():
            self._party.cancel()
        await ctx.reply("Стою на месте.")

    @command("sit", aliases=("сядь", "присядь"), cooldown=(3, 20.0), description="присесть рядом, если вы сидите")
    async def sit(self, ctx: Context) -> None:
        if not self.can_sit:
            await ctx.reply("В этом мире я не умею садиться, зато могу ходить за вами: !follow")
            return
        where = await self.where(ctx.user.id)
        if isinstance(where, AnchorPosition) and await self.sit_near(where):
            await ctx.reply("Подвинься - присяду рядом.")
        else:
            await ctx.reply("Сядьте на мебель, где есть второе место, и повторите команду.")

    # ---- связь -----------------------------------------------------------------------------

    @command("tell", aliases=("передай", "письмо"), cooldown=(3, 60.0), description="письмо тому, кого нет рядом: !tell имя текст")
    async def tell(self, ctx: Context) -> None:
        name, body = ctx.arg(0), " ".join(ctx.args[1:]).strip()
        if not name or not body:
            await ctx.reply("Формат: !tell имя текст письма")
            return
        found = self.find_profile(name)
        if found is None:
            await ctx.reply("Я не знаю такого игрока: он ещё не заходил при мне.")
            return
        user_id, _ = found
        if user_id == ctx.user.id:
            await ctx.reply("Письмо самому себе? Запишите в заметки.")
            return
        body = body[:MAIL_LENGTH]
        if user_id in self.room:
            ok = await self.attempt(self.api.whisper(user_id, f"Письмо от {ctx.user.username}: {body}"))
            await ctx.reply("Передал лично, он(а) здесь." if ok else "Не получилось передать, попробуйте ещё раз.")
            return
        letters = self.mail.setdefault(user_id, [])
        if len(letters) >= MAIL_LIMIT:
            await ctx.reply("Ящик получателя переполнен, пусть сначала прочитает письма.")
            return
        letters.append(Letter(ctx.user.username, body, time.time()))
        self._dirty = True
        await self.save()
        await ctx.reply(f"Письмо сохранено, передам, когда {name.lstrip('@')} появится.")

    @command("inbox", aliases=("почта", "письма"), cooldown=(3, 20.0), description="прочитать свои письма")
    async def inbox(self, ctx: Context) -> None:
        text = self.inbox_text(ctx.user.id)
        if ctx.whisper:
            await ctx.reply(text)
        else:
            await self.attempt(self.api.whisper(ctx.user.id, text))
            await ctx.reply("Отправил письма шёпотом." if text != "Писем нет." else text)

    @command("seen", aliases=("видели",), cooldown=(3, 20.0), description="когда был игрок: !seen имя")
    async def seen(self, ctx: Context) -> None:
        name = ctx.arg(0)
        if not name:
            await ctx.reply("Формат: !seen имя")
            return
        found = self.find_profile(name)
        if found is None:
            await ctx.reply("Такого игрока я не помню.")
        elif found[0] in self.room:
            await ctx.reply(f"{found[1].name} сейчас здесь!")
        else:
            await ctx.reply(f"{found[1].name} был(а) {ago(time.time() - found[1].last_seen)}.")

    @command("rules", aliases=("правила",), cooldown=(2, 30.0), description="правила комнаты")
    async def rules(self, ctx: Context) -> None:
        await ctx.reply(self.rules_text)

    # ---- владелец ---------------------------------------------------------------------------

    @command("say", aliases=("скажи",), owner_only=True, description="сказать от имени бота: !say текст")
    async def say_command(self, ctx: Context) -> None:
        text = ctx.rest()
        if text:
            await self.api.chat(text)

    @command("setrules", owner_only=True, description="сменить правила: !setrules текст")
    async def setrules(self, ctx: Context) -> None:
        text = ctx.rest().strip()
        if not text:
            await ctx.reply("Формат: !setrules текст правил")
            return
        self.rules_text = text[:400]
        await self.save()
        await ctx.reply("Правила обновлены.")

    @command("give", aliases=("выдай",), owner_only=True, description="выдать искры: !give имя число")
    async def give(self, ctx: Context) -> None:
        found = self.find_profile(ctx.arg(0) or "")
        amount = ctx.arg(1)
        if found is None or amount is None or not amount.lstrip("-").isdigit() or not -10000 <= int(amount) <= 10000:
            await ctx.reply("Формат: !give имя число (от -10000 до 10000)")
            return
        found[1].sparks = max(0, found[1].sparks + int(amount))
        self._dirty = True
        await self.save()
        await ctx.reply(f"{found[1].name}: теперь {sparks(found[1].sparks)}.")

    @command("status", aliases=("статус",), owner_only=True, description="состояние бота")
    async def status(self, ctx: Context) -> None:
        gold = await self.api.gold()
        uptime = int(time.monotonic() - self._started)
        total = sum(profile.sparks for profile in self.profiles.values())
        await ctx.reply(
            f"В сети {uptime // 3600} ч {uptime // 60 % 60} мин. В комнате людей: {len(self.humans())}. "
            f"Профилей: {len(self.profiles)}, искр в обороте: {total}. Золото бота: {gold}. Писем в ящиках: {sum(map(len, self.mail.values()))}."
        )

    @command("shutdown", aliases=("выключись",), owner_only=True, description="остановить бота")
    async def shutdown(self, ctx: Context) -> None:
        await ctx.reply("Ухожу на перерыв. До скорого!")
        await self.save()
        await self.stop()


# --------------------------------------------------------------------------------------
# Запуск
# --------------------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    token = os.environ.get("SUKARISEBOT_TOKEN", "").strip()
    if not token and sys.stdin.isatty():
        token = getpass.getpass("Токен бота (srbot_..., ввод скрыт): ").strip()
    if not token:
        raise SystemExit("Нужен токен бота: задайте переменную SUKARISEBOT_TOKEN или запустите файл в терминале.")
    room = os.environ.get("SUKARISEBOT_ROOM_ID", "").strip() or DEFAULT_ROOM
    url = os.environ.get("SUKARISEBOT_URL", "").strip() or DEFAULT_URL
    data = os.environ.get("FLUXUS_DATA", "").strip()
    try:
        (FluxusBot(data) if data else FluxusBot()).start(token=token, room_id=room, url=url)
    except ConnectionRefused as error:
        raise SystemExit(f"Сервер отказал: {error}") from error


if __name__ == "__main__":
    main()
