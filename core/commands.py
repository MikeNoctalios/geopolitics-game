"""Каталог системных команд Гейммастера и их исполнение.

Каждая команда — маленькая функция, возвращающая строку для лога. Если команду выполнить
нельзя (страна не найдена и т.п.), возвращается «⚠️ ...», а не молчаливый None, как раньше.
"""
import streamlit as st

from ai.client import get_ai_client, load_config
from core import world_ops as W
from core.military import (CATEGORIES, audit_military_catalog, ensure_military_loaded,
                           make_rd_project, normalize_military_category)

COMMAND_CATALOG_DOCS = """
CATALOG OF EXECUTABLE SYSTEM COMMANDS:

1. GEO_STATE:
   - DELETE_COUNTRY {"country": "<Nation>"}
   - SPAWN_COUNTRY {"name": "<Nation>", "region": "Европа"|"Азия"|"Америка"|"Ближний Восток", "regime": "<Regime>", "manpower": "<e.g. ~1 млн. чел.>"}
   - RENAME_COUNTRY {"old_name": "<Old>", "new_name": "<New>"}
   - SET_DATE {"date": "<e.g. 15 Мая 1941>"}

2. MILITARY_VPK:
   - AUDIT_ARMY {"country": "<Nation>"} -> Triggers full AI restructuring, deduplication, and era-balancing of the military catalog.
   - SET_MANPOWER {"country": "<Nation>", "manpower": "<e.g. ~850 тыс. чел.>"}
   - GRANT_EQUIPMENT {"country": "<Nation>", "name": "<Model>", "count": <int>, "category": "ground"|"infantry"|"air"|"navy", "type": "<Type>", "specs": "<Specs>"}
   - REMOVE_EQUIPMENT {"country": "<Nation>", "name": "<Model>"}
   - RENAME_EQUIPMENT {"country": "<Nation>", "old_name": "<Old>", "new_name": "<New>"}
   - ADD_RD_TEST {"country": "<Nation>", "name": "<Prototype Name>", "category": "ground"|"infantry"|"air"|"navy", "duration": "<e.g. 2 Дня or 1.5 Года>", "specs": "<Specs>", "status": "<Status>"}
   - COMPLETE_RD_TEST {"project_name": "<Project>"}

3. DOMESTIC & AGENDA:
   - ADD_ISSUE {"country": "<Nation>", "name": "<Task name>", "target_date": "<Deadline>", "status": "<Status>"}
   - DISMISS_ISSUE {"country": "<Nation>", "name": "<Task name>"}
   - CLEAR_ISSUES {"country": "<Nation>"}
   - SET_STATS {"country": "<Nation>", "stability": <int 0-100>, "war_support": <int 0-100>, "military_readiness": <int 0-100>}
   - SET_REGIME {"country": "<Nation>", "regime": "<Regime>", "faction": "<Faction>"}
   - SET_RESOURCES {"country": "<Nation>", "resources": "<e.g. Нефть: избыток, Сталь: норма>"}
   - TRIGGER_INTERNAL_EVENT {"title": "<Title>", "desc": "<Desc>", "type": "positive"|"negative", "impact": "<Impact>"}

4. NARRATIVE_NEWS & CONFERENCES:
   - PUBLISH_WORLD_NEWS {"title": "<Headline>", "desc": "<News Body>"}
   - SET_LORE_DIRECTIVE {"directive": "<Historical fact for all agents to remember>"}
   - START_CONFERENCE {"title": "<Title>", "initiator": "<Nation>", "participants": ["<Country 1>", "<Country 2>"], "topic": "<Agenda>", "secrecy": "Все"|"Только участники"}
"""

HANDLERS = {}


def command(name):
    def deco(fn):
        HANDLERS[name] = fn
        return fn
    return deco


def _ss():
    return st.session_state


def _target(p, key="country"):
    """Страна из параметров (по умолчанию — страна игрока) -> точное имя или None."""
    return W.resolve_country(p.get(key) or _ss().player_country)


def _no_country(p, key="country"):
    return f"⚠️ Держава «{p.get(key) or _ss().player_country}» не найдена в мире — команда пропущена"


def _military(country: str) -> dict:
    ensure_military_loaded(country)
    return _ss().countries[country]["military"]


# --------------------------------------------------------------------------- #
# 1. GEO_STATE
# --------------------------------------------------------------------------- #
@command("DELETE_COUNTRY")
def _delete_country(p):
    c = W.resolve_country(p.get("country"))
    if not c:
        return _no_country(p)
    W.delete_country(c)
    suffix = " Игроку будет предложено выбрать государство-преемника." if c == _ss().player_country else ""
    return f"❌ [Карта] Держава '{c}' ликвидирована.{suffix}"


@command("SPAWN_COUNTRY")
def _spawn_country(p):
    name = str(p.get("name") or "").strip()
    if not name:
        return "⚠️ SPAWN_COUNTRY: не указано название"
    if name in _ss().countries:
        return f"⚠️ Держава '{name}' уже существует"
    _ss().countries[name] = W.new_country(name, p)
    return f"🌟 [Карта] Образовано новое государство: '{name}'"


@command("RENAME_COUNTRY")
def _rename_country(p):
    old = W.resolve_country(p.get("old_name"))
    new = str(p.get("new_name") or "").strip()
    if not old:
        return _no_country(p, "old_name")
    if not W.rename_country(old, new):
        return f"⚠️ Не удалось переименовать '{old}' (имя '{new}' пустое или занято)"
    return f"🏷️ [Карта] Держава '{old}' переименована в '{new}'"


@command("SET_DATE")
def _set_date(p):
    if not p.get("date"):
        return "⚠️ SET_DATE: не указана дата"
    _ss().current_date = str(p["date"])
    return f"📅 [Календарь] Дата мира установлена на: {p['date']}"


# --------------------------------------------------------------------------- #
# 2. MILITARY_VPK
# --------------------------------------------------------------------------- #
@command("AUDIT_ARMY")
def _audit_army(p):
    c = _target(p)
    if not c:
        return _no_country(p)
    cfg = load_config()
    if not cfg.get("api_key"):
        return "⚠️ [ВПК] Ошибка аудита: отсутствует API ключ"
    mil = _military(c)
    with st.spinner(f"Аудит ВПК: {c}..."):
        audited, err = audit_military_catalog(
            get_ai_client(cfg["api_key"], cfg["base_url"]), cfg["model_name"], c, mil,
            _ss().current_date, _ss().countries[c].get("stats", {}).get("manpower_approx", "~500 тыс. чел."))
    if err:
        return f"⚠️ [ВПК] Аудит '{c}' не удался, реестр не изменён: {err}"
    _ss().countries[c]["military"] = audited
    return f"🪖 [ВПК] Проведен полный аудит и реорганизация реестра вооружений державы '{c}'"


@command("SET_MANPOWER")
def _set_manpower(p):
    c = _target(p)
    if not c:
        return _no_country(p)
    mp = str(p.get("manpower") or "~800 тыс. чел.")
    _ss().countries[c].setdefault("stats", {})["manpower_approx"] = mp
    return f"📊 [Армия] Численность кадровой армии '{c}' установлена на: {mp}"


@command("GRANT_EQUIPMENT")
def _grant_equipment(p):
    c = _target(p)
    if not c:
        return _no_country(p)
    mil = _military(c)
    name = str(p.get("name") or "Новый образец")
    count = W.to_int(p.get("count", 100), 100)
    cat = normalize_military_category(p.get("category", "ground"))
    mil.setdefault(cat, []).append({
        "name": name, "type": str(p.get("type") or "Боевое оснащение"), "count": count,
        "production": True, "in_service": True,
        "specs": str(p.get("specs") or "Выдано по распоряжению Гейммастера."),
        "evaluation": "Состоит на вооружении.", "is_known_globally": True,
    })
    return f"🪖 [ВПК] Для '{c}' начислено: {name} ({count:,} ед.) [{cat}]"


@command("REMOVE_EQUIPMENT")
def _remove_equipment(p):
    c = _target(p)
    name = p.get("name")
    if not c:
        return _no_country(p)
    if not name:
        return "⚠️ REMOVE_EQUIPMENT: не указано название образца"
    mil = _military(c)
    removed = 0
    for cat in CATEGORIES:
        before = len(mil.get(cat, []))
        mil[cat] = [it for it in mil.get(cat, []) if it.get("name") != name]
        removed += before - len(mil[cat])
    if not removed:
        return f"⚠️ [ВПК] Образец '{name}' у '{c}' не найден"
    return f"🗑️ [ВПК] Образец '{name}' списан из арсенала '{c}'"


@command("RENAME_EQUIPMENT")
def _rename_equipment(p):
    c = _target(p)
    old, new = p.get("old_name"), str(p.get("new_name") or "").strip()
    if not c:
        return _no_country(p)
    mil = _military(c)
    hits = [it for cat in CATEGORIES for it in mil.get(cat, []) if it.get("name") == old]
    if not hits or not new:
        return f"⚠️ [ВПК] Образец '{old}' у '{c}' не найден (или не задано новое имя)"
    for it in hits:
        it["name"] = new
    for proj in _ss().rd_projects:     # проекты ссылаются на технику по имени
        if proj.get("base_equipment") == old:
            proj["base_equipment"] = new
    return f"✏️ [ВПК] '{old}' переименован в '{new}' ({c})"


@command("ADD_RD_TEST")
def _add_rd_test(p):
    name = p.get("name", "Перспективный образец")
    _ss().rd_projects.append(make_rd_project(
        name, name, p.get("category", "navy"), p.get("type", "Опытный прототип"),
        p.get("duration", "1 Год"), p.get("progress", 15), p.get("status", "Полигонные испытания"),
        p.get("specs", "Проект на полигоне КБ."),
        "Проводятся замеры гидродинамики и полигонные тесты узлов."))
    return f"🎯 [Полигон КБ] Запущен проект испытаний: '{name}' (Срок: {p.get('duration', '1 Год')})"


@command("COMPLETE_RD_TEST")
def _complete_rd_test(p):
    needle = str(p.get("project_name") or "").lower()
    for proj in _ss().rd_projects:
        if needle and needle in proj.get("name", "").lower():
            proj.update(progress=100, ready_for_tender=True, status="Госиспытания успешно завершены")
            return f"🏆 [Полигон КБ] Проект '{proj['name']}' досрочно завершил испытания и готов к принятию!"
    return f"⚠️ [Полигон КБ] Проект «{p.get('project_name')}» не найден"


# --------------------------------------------------------------------------- #
# 3. DOMESTIC & AGENDA
# --------------------------------------------------------------------------- #
@command("ADD_ISSUE")
def _add_issue(p):
    c = _target(p)
    if not c:
        return _no_country(p)
    name = p.get("name") or p.get("title") or "Отслеживание государственной программы"
    target = p.get("target_date") or p.get("duration") or "Постоянно"
    status = p.get("status") or "Активно"
    _ss().countries[c].setdefault("current_issues", []).append(
        {"name": str(name), "start_date": _ss().current_date, "target_date": str(target), "status": str(status)})
    return f"📌 [Повестка дня] Для '{c}' добавлена задача: '{name}' (Дедлайн: {target} | Статус: {status})"


@command("DISMISS_ISSUE")
def _dismiss_issue(p):
    c = _target(p)
    name = p.get("name") or p.get("title")
    if not c:
        return _no_country(p)
    if not name:
        return "⚠️ DISMISS_ISSUE: не указана задача"
    cur = _ss().countries[c].get("current_issues", [])
    keep = [x for x in cur if str(name).lower() not in x.get("name", "").lower()]
    if len(keep) == len(cur):
        return f"⚠️ [Повестка дня] Задача «{name}» у '{c}' не найдена"
    _ss().countries[c]["current_issues"] = keep
    return f"✅ [Повестка дня] Из повестки '{c}' снята задача: '{name}'"


@command("CLEAR_ISSUES")
def _clear_issues(p):
    c = _target(p)
    if not c:
        return _no_country(p)
    _ss().countries[c]["current_issues"] = []
    return f"🧹 [Повестка дня] Повестка дня державы '{c}' полностью очищена"


@command("SET_STATS")
def _set_stats(p):
    c = _target(p)
    if not c:
        return _no_country(p)
    stats = _ss().countries[c].setdefault("stats", {})
    stats.update(W.clean_stats_patch(p))      # значения зажимаются в 0..100, мусор отбрасывается
    if p.get("manpower"):
        stats["manpower_approx"] = str(p["manpower"])
    return f"⚙️ [Параметры] Обновлены показатели державы '{c}'"


@command("SET_REGIME")
def _set_regime(p):
    c = _target(p)
    if not c:
        return _no_country(p)
    for k in ("regime", "faction"):
        if k in p:
            _ss().countries[c][k] = str(p[k])
    return f"👑 [Власть] Для '{c}' установлен режим: {_ss().countries[c].get('regime')}"


@command("SET_RESOURCES")
def _set_resources(p):
    c = _target(p)
    if not c:
        return _no_country(p)
    _ss().countries[c]["resources"] = str(p.get("resources", ""))
    return f"📦 [Ресурсы] Обновлена ресурсная база державы '{c}'"


@command("TRIGGER_INTERNAL_EVENT")
def _internal_event(p):
    ev_type = "negative" if str(p.get("type")) == "negative" else "positive"
    _ss().internal_events.append({
        "title": str(p.get("title") or "Внутреннее событие"), "desc": str(p.get("desc") or ""),
        "type": ev_type, "impact": str(p.get("impact") or "")})
    return f"⚡ [Кабинет] Внутреннее происшествие: {p.get('title')}"


# --------------------------------------------------------------------------- #
# 4. NARRATIVE_NEWS & CONFERENCES
# --------------------------------------------------------------------------- #
@command("PUBLISH_WORLD_NEWS")
def _publish_news(p):
    title = p.get("title", "Мировая сенсация")
    W.add_world_event(title, p.get("desc", ""))
    return f"📰 [Мировые Новости] Опубликована статья: «{title}»"


@command("SET_LORE_DIRECTIVE")
def _lore(p):
    if not p.get("directive"):
        return "⚠️ SET_LORE_DIRECTIVE: пустая директива"
    W.add_arc(p["directive"])
    return "🧠 [Лор] Директива принята ко сведению всеми агентами"


@command("START_CONFERENCE")
def _start_conference(p):
    if _ss().get("active_conference"):
        return "⚠️ [Саммит] Уже идёт другой саммит — сначала завершите его"
    me = _ss().player_country
    initiator = W.resolve_country(p.get("initiator")) or me
    raw = p.get("participants") if isinstance(p.get("participants"), list) else []
    parts = [c for c in (W.resolve_country(x) for x in raw) if c]
    if me not in parts:          # интерфейс саммита рассчитан на участие игрока
        parts.append(me)
    title = p.get("title", "Международный саммит")
    _ss().active_conference = W.new_conference(
        title, initiator, parts or [me], p.get("topic", "Урегулирование кризиса"), p.get("secrecy", "Все"))
    return f"🏛 [Саммит] Созвана международная конференция: «{title}»"


# --------------------------------------------------------------------------- #
def execute_single_command(cmd_name: str, params: dict):
    cmd = str(cmd_name).upper().strip()
    handler = HANDLERS.get(cmd)
    if not handler:
        return f"⚠️ Неизвестная команда: {cmd_name}"
    return handler(params if isinstance(params, dict) else {})


def execute_command_pipeline(commands_list: list) -> list:
    if not isinstance(commands_list, list) or not commands_list:
        return ["Предупреждение: Гейммастер не вернул ни одной команды."]
    logs = []
    for item in commands_list:
        if not isinstance(item, dict) or not item.get("command"):
            continue
        try:
            res = execute_single_command(item["command"], item.get("params", {}))
        except Exception as e:     # одна битая команда не должна ронять остальные
            res = f"⚠️ Ошибка в команде {item['command']}: {type(e).__name__}: {e}"
        if res:
            logs.append(res)
    return logs
