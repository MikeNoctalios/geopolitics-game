"""Настройки оформления стола (цвета, шрифты по категориям, размеры) и загруженные пользователем шрифты."""
import json
import os
import re
import time

from ai.client import BASE_DIR

PREFS_FILE = os.path.join(BASE_DIR, "ui_prefs.json")
USER_FONTS_DIR = os.path.join(BASE_DIR, "fonts")
BUNDLED_FONTS_DIR = os.path.join(BASE_DIR, "web", "fonts")

CLOTHS = ("green", "dark", "olive", "grey", "blue", "desert", "black", "pink", "horizon", "brown", "burgundy")   # + «custom» = 12 ячеек, два ряда по шесть
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
TYPEWRITERS = ("black", "green", "blue", "red", "cream", "steel")
CATEGORIES = {                       # id -> подпись в настройках (порядок = порядок в приложении «Оформление»)
    "news_head": "Шапка и заголовки газеты", "news_body": "Текст газеты", "title": "Заголовки страниц и листов",
    "hand": "Рукописный текст (шапка, блокнот)", "label": "Надписи (меню, кнопки, подписи печатей)",
    "stamp": "Штампы", "tech": "Технические листы (ТТХ, повестка)", "type": "Печатная машинка",
    "ui": "Интерфейс (книга, телефон)", "numerals": "Цифры", "seals": "Числа в печатях",
}


def _font(file, name, cyrillic, faces=None, adjust=100):
    """faces — файлы начертаний; weight 100 900 у одиночных шрифтов, чтобы браузер не рисовал «поддельный» жирный."""
    return {"file": file, "name": name, "cyrillic": cyrillic, "adjust": adjust,
            "faces": faces or [{"file": file, "weight": "100 900", "style": "normal"}]}


BUNDLED = [
    _font("PlayfairDisplay-VariableFont_wght.ttf", "Playfair Display", True, adjust=100, faces=[
        {"file": "PlayfairDisplay-VariableFont_wght.ttf", "weight": "400 900", "style": "normal"},
        {"file": "PlayfairDisplay-Italic-VariableFont_wght.ttf", "weight": "400 900", "style": "italic"}]),
    _font("CormorantGaramond-VariableFont_wght.ttf", "Cormorant Garamond", True, adjust=118, faces=[
        {"file": "CormorantGaramond-VariableFont_wght.ttf", "weight": "300 700", "style": "normal"},
        {"file": "CormorantGaramond-Italic-VariableFont_wght.ttf", "weight": "300 700", "style": "italic"}]),
    _font("Caveat-VariableFont_wght.ttf", "Caveat", True, adjust=114,
          faces=[{"file": "Caveat-VariableFont_wght.ttf", "weight": "400 700", "style": "normal"}]),
    _font("AmaticSC-Regular.ttf", "Amatic SC", True, adjust=135, faces=[
        {"file": "AmaticSC-Regular.ttf", "weight": "100 600", "style": "normal"},
        {"file": "AmaticSC-Bold.ttf", "weight": "700 900", "style": "normal"}]),
    _font("GreatVibes-Regular.ttf", "Great Vibes", True, adjust=122),
    _font("DelaGothicOne-Regular.ttf", "Dela Gothic One", True, adjust=92),
    _font("Oswald-VariableFont_wght.ttf", "Oswald", True, adjust=100,
          faces=[{"file": "Oswald-VariableFont_wght.ttf", "weight": "200 700", "style": "normal"}]),
    _font("RussoOne-Regular.ttf", "Russo One", True, adjust=100),
    # шрифты без кириллицы (личное использование): применяются только к цифрам и латинице
    _font("ForgeGarage.otf", "Forge Garage Blackletter", False),
    _font("Undesa.ttf", "UNDESA", False),
    _font("CiaoMilan.ttf", "CiaoMilan", False),
    _font("VintageChristmas.ttf", "Vintage Christmas", False),
]
PREFS_VERSION = 2                    # при смене набора шрифтов по умолчанию старые назначения сбрасываются
DEFAULTS = {
    "version": PREFS_VERSION,
    "cloth": "green", "cloth_custom": None, "typewriter": "black", "online_fonts": False,
    "fonts": {c: "default" for c in CATEGORIES} | {
        "news_head": "bundled:PlayfairDisplay-VariableFont_wght.ttf", "news_body": "bundled:CormorantGaramond-VariableFont_wght.ttf",
        "title": "bundled:GreatVibes-Regular.ttf", "hand": "bundled:Caveat-VariableFont_wght.ttf",
        "label": "bundled:AmaticSC-Regular.ttf", "stamp": "bundled:DelaGothicOne-Regular.ttf",
        "tech": "bundled:Oswald-VariableFont_wght.ttf",
        "numerals": "bundled:ForgeGarage.otf", "seals": "bundled:VintageChristmas.ttf"},
    "scale": {c: 1.0 for c in CATEGORIES},
}
FONT_FILE_RE = re.compile(r"^[\w .()\-]{1,80}\.(ttf|otf|woff2?|TTF|OTF)$")
MAX_FONT_BYTES = 8 * 1024 * 1024
MAGIC = (b"\x00\x01\x00\x00", b"OTTO", b"wOFF", b"wOF2", b"true")


def _valid_font_id(fid) -> bool:
    if fid == "default":
        return True
    kind, _, file = str(fid).partition(":")
    return kind in ("bundled", "user") and bool(FONT_FILE_RE.match(file))


def load() -> dict:
    prefs = json.loads(json.dumps(DEFAULTS))
    try:
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    if data.get("version") != PREFS_VERSION:      # старый файл: шрифты и размеры возвращаем к новым значениям по умолчанию
        data.pop("fonts", None); data.pop("scale", None)
    return _merge(prefs, data)


def _merge(prefs: dict, data: dict) -> dict:
    custom = data.get("cloth_custom")
    if isinstance(custom, str) and HEX_RE.match(custom):
        prefs["cloth_custom"] = custom.lower()
    if data.get("cloth") in CLOTHS or (data.get("cloth") == "custom" and prefs["cloth_custom"]):
        prefs["cloth"] = data["cloth"]
    if data.get("typewriter") in TYPEWRITERS:
        prefs["typewriter"] = data["typewriter"]
    if isinstance(data.get("online_fonts"), bool):
        prefs["online_fonts"] = data["online_fonts"]
    for cat in CATEGORIES:
        fid = (data.get("fonts") or {}).get(cat)
        if fid is not None and _valid_font_id(fid):
            prefs["fonts"][cat] = fid
        sc = (data.get("scale") or {}).get(cat)
        if isinstance(sc, (int, float)) and not isinstance(sc, bool):
            prefs["scale"][cat] = round(max(0.6, min(2.0, float(sc))), 2)
    return prefs


def update(patch: dict) -> dict:
    prefs = load()
    patch = patch if isinstance(patch, dict) else {}
    merged = _merge(json.loads(json.dumps(prefs)), patch)
    tmp = PREFS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PREFS_FILE)
    return merged


def user_fonts() -> list:
    try:
        names = sorted(os.listdir(USER_FONTS_DIR))
    except OSError:
        return []
    return [{"file": n, "name": os.path.splitext(n)[0], "cyrillic": None} for n in names if FONT_FILE_RE.match(n)]


def save_user_font(name: str, data: bytes) -> str:
    name = os.path.basename(str(name or "")).strip()
    if not FONT_FILE_RE.match(name):
        raise ValueError("Допустимы файлы .ttf, .otf, .woff, .woff2 с простым именем")
    if not data or len(data) > MAX_FONT_BYTES:
        raise ValueError("Файл пуст или больше 8 МБ")
    if not data[:4] in MAGIC:
        raise ValueError("Это не шрифт: неверная сигнатура файла")
    os.makedirs(USER_FONTS_DIR, exist_ok=True)
    base, ext = os.path.splitext(name)
    final, i = name, 1
    while os.path.exists(os.path.join(USER_FONTS_DIR, final)):
        i += 1
        final = f"{base} ({i}){ext}"
    tmp = os.path.join(USER_FONTS_DIR, final + ".part")
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, os.path.join(USER_FONTS_DIR, final))
    return final


def delete_user_font(name: str):
    name = os.path.basename(str(name or ""))
    if not FONT_FILE_RE.match(name):
        raise ValueError("Недопустимое имя файла")
    path = os.path.join(USER_FONTS_DIR, name)
    if os.path.isfile(path):
        os.remove(path)
    prefs = load()                       # категории, которые использовали этот шрифт, возвращаются к стандартному
    reset = {c: "default" for c, fid in prefs["fonts"].items() if fid == f"user:{name}"}
    if reset:
        update({"fonts": reset})
