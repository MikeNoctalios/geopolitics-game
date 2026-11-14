"""Работа с датами мира. Дата в игре — свободный текст вроде «15 Мая 1941»."""
import re

_YEAR_RE = re.compile(r"(?<!\d)(1\d{3}|20\d{2})(?!\d)")
_MONTH_STEMS = (("январ", 1), ("феврал", 2), ("март", 3), ("апрел", 4), ("мая", 5), ("май", 5),
                ("июн", 6), ("июл", 7), ("август", 8), ("сентябр", 9), ("октябр", 10),
                ("ноябр", 11), ("декабр", 12))


def extract_year(date_str, default: int = 1935) -> int:
    m = _YEAR_RE.search(str(date_str))
    return int(m.group(1)) if m else default


def has_year(date_str) -> bool:
    return bool(_YEAR_RE.search(str(date_str)))


def parse_date(date_str) -> tuple:
    """(год, месяц, день); неизвестные части = None."""
    s = str(date_str).lower()
    ym = _YEAR_RE.search(s)
    year = int(ym.group(1)) if ym else None
    month = next((n for w in re.findall(r"[а-яё]+", s) for stem, n in _MONTH_STEMS if w.startswith(stem)), None)
    day = None
    m = re.match(r"\s*(\d{1,2})(?!\d)", s)
    if m and 1 <= int(m.group(1)) <= 31:
        day = int(m.group(1))
    return year, month, day


def is_date_regression(old, new) -> bool:
    """True, если новая дата заведомо раньше старой (сравниваем только известные части)."""
    for a, b in zip(parse_date(old), parse_date(new)):
        if a is None or b is None:
            return False
        if b != a:
            return b < a
    return False
