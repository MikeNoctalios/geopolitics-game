"""Реестры вооружений: генерация, аудит, санитайзер и фабрика НИОКР-проектов."""
import json
import re
import uuid

import streamlit as st

from ai.client import call_json, get_ai_client, load_config
from ai.prompts import get_alt_history_directive
from core.state import get_scenario_world_context
from core.time_system import extract_year
from core.world_ops import to_int

CATEGORIES = ("infantry", "ground", "air", "navy")
LEGACY_PENDING = "genit"   # так старые сохранения/сценарии помечали «реестр ещё не создан»

LANDLOCKED_NATIONS = {
    "Люксембург", "Сан-Марино", "Ватикан", "Лихтенштейн", "Андорра", "Швейцария",
    "Австрия", "Чехословакия", "Венгрия", "Боливия", "Парагвай", "Монголия",
    "Монгольская Народная Республика", "Тува", "Тувинская Народная Республика",
    "Тибет", "Афганистан", "Непал", "Бутан", "Синьцзян"
}
MICROSTATES = {"Сан-Марино", "Ватикан", "Монако", "Лихтенштейн", "Андорра", "Люксембург"}

_ITEM_SCHEMA = ('{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, '
                '"specs": str, "evaluation": str, "is_known_globally": bool}')
CATALOG_SCHEMA = "{\n" + ",\n".join(f'  "{c}": [{_ITEM_SCHEMA}]' for c in CATEGORIES) + "\n}"

_NAVY = re.compile(r"флот|корабл|эсминц|линкор|подлодк|субмарин|катер|крейсер|авианос|\b(navy|ship|submarine)\b")
_AIR = re.compile(r"авиа|самол[её]т|истребител|бомбардировщик|штурмовик|вертол[её]т|\b(air|plane|aircraft)\b")
_INF = re.compile(r"пехот|винтов|автомат|пулем[её]т|стрелк|снаряж|\b(infantry|small_arms)\b")


def normalize_military_category(raw_cat) -> str:
    """Любую категорию от ИИ/игрока -> одна из четырёх системных (единственная копия функции).

    Порядок важен: «авианосец» — флот, а не авиация; «бомбардировщик» — авиация, а не пехота.
    """
    c = str(raw_cat).lower().strip()
    if _NAVY.search(c):
        return "navy"
    if _AIR.search(c):
        return "air"
    if _INF.search(c):
        return "infantry"
    return "ground"   # танки, артиллерия, ПВО, тягачи


# --------------------------------------------------------------------------- #
# Санитайзер: всё, что пришло от LLM или из старого сохранения, приводим к типам
# --------------------------------------------------------------------------- #
def clean_item(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "name": str(raw.get("name") or "Образец"),
        "type": str(raw.get("type") or ""),
        "count": to_int(raw.get("count", 0)),
        "production": bool(raw.get("production", False)),
        "in_service": bool(raw.get("in_service", True)),
        "specs": str(raw.get("specs") or ""),
        "evaluation": str(raw.get("evaluation") or ""),
        "is_known_globally": bool(raw.get("is_known_globally", True)),
    }


def clean_catalog(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = {c: [] for c in CATEGORIES}
    for cat in CATEGORIES:
        items = raw.get(cat)
        out[cat] = [clean_item(i) for i in items if isinstance(i, dict)] if isinstance(items, list) else []
    return out


def is_pending(mil) -> bool:
    return mil is None or mil == LEGACY_PENDING or not isinstance(mil, dict)


# --------------------------------------------------------------------------- #
# Генерация и аудит
# --------------------------------------------------------------------------- #
def _lore_block() -> str:
    try:
        return get_alt_history_directive(st.session_state.get("is_alt_history", False),
                                         get_scenario_world_context())
    except Exception:
        return ""


def get_smart_fallback_military(country_name, date_str):
    year = extract_year(date_str)
    is_landlocked = country_name in LANDLOCKED_NATIONS
    is_micro = country_name in MICROSTATES

    def item(name, typ, count, specs, ev, production=True):
        return {"name": name, "type": typ, "count": count, "production": production, "in_service": True,
                "specs": specs, "evaluation": ev, "is_known_globally": True}

    infantry = [item(f"Штатные винтовки ({country_name})", "Винтовки пехоты", 500 if is_micro else 150000,
                     "Калибр 6.5-7.92 мм, магазинное питание", "Штатное вооружение пехоты.",
                     production=not is_micro)]
    ground, air, navy = [], [], []
    if not is_micro:
        if year >= 1916:
            ground.append(item(f"Легкая бронетехника ({year} г.)", "Бронеавтомобиль / Танк", 45,
                               "Пулеметное или 37-мм пушечное вооружение", "Охранение и разведка."))
        ground.append(item("Полевая дивизионная артиллерия", "Полевая артиллерия", 140,
                           "Калибр 75-76 мм", "Основа дивизионного огня."))
        if year >= 1911:
            air.append(item(f"Авиаотряд ({country_name})", "Авиация", 30,
                            "Скорость 180-340 км/ч", "Разведка и связь."))
        if not is_landlocked:
            navy.append(item(f"Патрульные канонерки ({country_name})", "Эсминец / Канонерка", 4,
                             "Орудия 75-102 мм", "Охрана территориальных вод."))
    return {"infantry": infantry, "ground": ground, "air": air, "navy": navy}


def _geo_rules(country_name, year, manpower_str):
    landlocked = country_name in LANDLOCKED_NATIONS
    micro = country_name in MICROSTATES
    return (
        "NATION IS LANDLOCKED! 'navy' array MUST be strictly empty `[]`." if landlocked
        else "COASTAL nation: include realistic coastal/naval craft if appropriate, or `[]` if none.",
        f"Year is {year}! Before 1916 tanks did not exist ('ground' = artillery/cavalry only). "
        f"Before 1911 planes did not exist ('air' = `[]`). NO anachronistic or futuristic tech!",
        f"MICROSTATE ({manpower_str}): 50-800 rifles total, 0 tanks, 0 planes, 0 warships!" if micro
        else f"Regular nation scale: {manpower_str}. Rich, historically authentic, diverse arsenal.",
    )


def audit_military_catalog(client, model, country_name, current_military, date_str, manpower_str):
    """(каталог, ошибка). При сбое возвращает прежний каталог и текст ошибки."""
    year = extract_year(date_str)
    geo, era, scale = _geo_rules(country_name, year, manpower_str)
    prompt = f"""
    You are the SUPREME GENERAL INSPECTOR OF ARMAMENTS.
    {_lore_block()}
    Audit, clean, restructure, and balance the military catalog for {country_name} as of {date_str} (Year: {year}).

    Raw Catalog:
    {json.dumps(current_military, ensure_ascii=False)}

    AUDIT MANDATES:
    1. ALL text MUST BE IN FLUENT RUSSIAN.
    2. RECLASSIFY: rifles/machine guns -> 'infantry'; tanks, artillery, SPGs, anti-aircraft guns -> 'ground'; aircraft -> 'air'; ships (incl. carriers) -> 'navy'.
    3. GEOGRAPHY: {geo}
    4. SCALE: {scale}
    5. ERA INTEGRITY: {era}
    6. Merge duplicates. Preserve 'in_service' and 'production' flags.

    Return STRICTLY valid JSON:
    {CATALOG_SCHEMA}
    """
    res, _ = call_json(client, model, prompt, temperature=0.2, max_attempts=2)
    if res.get("_error") or not any(c in res for c in CATEGORIES):
        return current_military, res.get("_error") or "ответ без категорий вооружения"
    return clean_catalog(res), None


def audit_military_catalog_ai(client, model, country_name, current_military, date_str, manpower_str):
    """Совместимая обёртка: только каталог (при сбое — прежний)."""
    return audit_military_catalog(client, model, country_name, current_military, date_str, manpower_str)[0]


def generate_military_for_country(client, model, country_name, date_str, manpower_str):
    year = extract_year(date_str)
    geo, era, scale = _geo_rules(country_name, year, manpower_str)
    prompt = f"""
    You are an expert military historian. Generate an authentic, diverse, era-accurate military catalog for {country_name} as of {date_str}.
    {_lore_block()}
    STRICT RULES:
    1. {geo}
    2. {era}
    3. {scale} Provide 4-8 distinct items across active categories.
    4. ALL text values MUST be written in Russian!

    Return STRICTLY valid JSON:
    {CATALOG_SCHEMA}
    """
    res, _ = call_json(client, model, prompt, temperature=0.3, max_attempts=2)
    if res.get("_error") or not any(res.get(c) for c in CATEGORIES):
        return get_smart_fallback_military(country_name, date_str)
    return clean_catalog(res)


def ensure_military_loaded(country_name):
    """Создаёт реестр, только если его ещё нет. Пустой реестр (игрок всё списал) — не повод генерировать заново."""
    c_data = st.session_state.countries.get(country_name)
    if c_data is None or not is_pending(c_data.get("military")):
        return
    date = st.session_state.current_date
    manpower = c_data.get("stats", {}).get("manpower_approx", "~100 тыс. чел.")
    cfg = load_config()
    catalog = None
    if cfg.get("api_key"):
        with st.spinner(f"Формируется реестр вооружений: {country_name}..."):
            try:
                catalog = generate_military_for_country(
                    get_ai_client(cfg["api_key"], cfg["base_url"]), cfg["model_name"],
                    country_name, date, manpower)
            except Exception:
                catalog = None
    c_data["military"] = catalog or get_smart_fallback_military(country_name, date)


# --------------------------------------------------------------------------- #
# НИОКР
# --------------------------------------------------------------------------- #
def make_rd_project(name, base_equipment, category, type_="Опытный прототип", target_date="1 Год",
                    progress=15, status="Проектирование чертежей", specs="", report="") -> dict:
    return {
        "id": f"proj_{uuid.uuid4().hex[:8]}",   # раньше len(list)+1 → дубли id после удалений
        "name": str(name),
        "base_equipment": str(base_equipment),
        "category": normalize_military_category(category),
        "type": str(type_),
        "start_date": st.session_state.current_date,
        "target_date": str(target_date),
        "progress": max(0, min(100, to_int(progress, 15))),
        "status": str(status),
        "specs": str(specs),
        "polygon_report": str(report or "Конструкторское бюро приступило к эскизам."),
        "ready_for_tender": False,
    }
