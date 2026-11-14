"""Армия и ВПК для веб-интерфейса: реестр, консервация, модернизация, полигон, разведка.
Правила перенесены из прежней Streamlit-вкладки; форма данных — как ждёт web/js/army.js."""
import streamlit as st

from ai.client import get_ai_client, load_config
from core.errors import GameError
from core.military import CATEGORIES, LANDLOCKED_NATIONS, audit_military_catalog, ensure_military_loaded, make_rd_project
from core.world_ops import to_int

TIME_MAP = {"infantry": "9 Месяцев", "ground": "1.5 Года", "air": "2 Года", "navy": "3 Года"}


def _ss():
    return st.session_state


def _mil(country=None) -> dict:
    ss = _ss()
    name = country or ss.player_country
    ensure_military_loaded(name)
    c = ss.countries[name]
    if not isinstance(c.get("military"), dict):
        c["military"] = {k: [] for k in CATEGORIES}
    return c["military"]


def view() -> dict:
    """Плоский список items (индекс idx — позиция внутри своей категории) и проекты полигона."""
    ss = _ss()
    mil, me = _mil(), ss.countries[ss.player_country]
    items = []
    for cat in CATEGORIES:
        for i, eq in enumerate(mil.get(cat, [])):
            items.append({
                "cat": cat, "idx": i, "name": str(eq.get("name", "Образец")), "type": str(eq.get("type", "")),
                "count": to_int(eq.get("count", 0)), "production": bool(eq.get("production")),
                "in_service": eq.get("in_service", True) is not False, "specs": str(eq.get("specs", "")),
                "evaluation": str(eq.get("evaluation", "")),
                "in_rd": any(p.get("base_equipment") == eq.get("name") for p in ss.rd_projects)})
    projects = []
    for i, p in enumerate(ss.rd_projects):
        prog = max(0, min(100, to_int(p.get("progress", 10), 10)))
        projects.append({"idx": i, "id": p.get("id"), "name": str(p.get("name", "")), "base": str(p.get("base_equipment", "")),
                         "type": str(p.get("type", "")), "target_date": str(p.get("target_date", "")), "progress": prog,
                         "status": str(p.get("status", "")), "specs": str(p.get("specs", "")), "report": str(p.get("polygon_report", "")),
                         "ready": bool(p.get("ready_for_tender")) or prog >= 100, "category": p.get("category", "ground")})
    return {"country": ss.player_country, "manpower": me.get("stats", {}).get("manpower_approx", "Неизвестно"),
            "items": items, "projects": projects, "landlocked": ss.player_country in LANDLOCKED_NATIONS}


def _item(cat, idx, name):
    mil = _mil()
    try:
        i = int(idx)
    except (TypeError, ValueError):
        raise GameError("Реестр изменился — обновите лист")
    if cat not in CATEGORIES or not 0 <= i < len(mil.get(cat, [])) or mil[cat][i].get("name") != name:
        raise GameError("Реестр изменился — обновите лист")     # лист на экране устарел
    return mil, mil[cat][i], i


def act(kind, cat, idx, name, value=None) -> str:
    mil, eq, i = _item(cat, idx, name)
    ss = _ss()
    if kind == "stop":
        if not eq.get("production"):
            raise GameError("Производство уже остановлено")
        eq["production"] = False
        return f"{name}: выпуск остановлен"
    if kind == "start":
        eq["production"] = True
        return f"{name}: выпуск возобновлён"
    if kind == "moth":
        eq["in_service"], eq["production"] = False, False
        return f"{name}: на консервации"
    if kind == "unmoth":
        eq["in_service"] = True
        return f"{name}: возвращён в строй"
    if kind == "scrap":
        if eq.get("in_service", True):
            raise GameError("В утиль отправляют только технику со склада консервации")
        mil[cat].pop(i)
        return f"{name}: отправлен в утиль"
    if kind == "rename":
        new_name = str(value or "").strip()
        if not new_name:
            raise GameError("Название не может быть пустым")
        new_name = new_name[:80]
        for p in ss.rd_projects:                       # проекты ссылаются на технику по имени
            if p.get("base_equipment") == name:
                p["base_equipment"] = new_name
        eq["name"] = new_name
        return f"Переименовано: {new_name}"
    if kind == "modernize":
        if any(p.get("base_equipment") == name for p in ss.rd_projects):
            raise GameError("КБ уже ведёт разработку на этой платформе")
        deep = not eq.get("in_service", True)
        ss.rd_projects.append(make_rd_project(
            f"{'Глубокая модернизация' if deep else 'Модификация'} {name}", name, cat, eq.get("type", ""),
            TIME_MAP.get(cat, "1 Год"), 20 if deep else 15,
            "Разборка образца и замена узлов" if deep else "Проектирование чертежей",
            f"Капитальная модернизация со складов консервации: {name}" if deep else f"Улучшенный вариант платформы {name}",
            "Проводятся испытания узлов на износ." if deep else ""))
        return f"Заявка передана в КБ. Срок НИОКР: {TIME_MAP.get(cat, '1 Год')}"
    raise GameError("Неизвестное действие")


def project_act(kind, idx, value=None) -> str:
    projects = _ss().rd_projects
    try:
        i = int(idx)
    except (TypeError, ValueError):
        raise GameError("Список проектов изменился — обновите лист")
    if not 0 <= i < len(projects):
        raise GameError("Список проектов изменился — обновите лист")
    proj = projects[i]
    if not (proj.get("ready_for_tender") or to_int(proj.get("progress", 0)) >= 100):
        raise GameError("Проект ещё в работе: действия с ним доступны после завершения испытаний")   # как в исходной вкладке
    if kind == "cancel":
        projects.pop(i)
        return "Проект закрыт"
    if kind == "refine":
        proj.update(progress=75, ready_for_tender=False, status="Устранение полигонных замечаний")
        return "Проект отправлен на доработку (+6 мес.)"
    if kind == "adopt":
        name = str(value or "").strip()[:80] or str(proj.get("name", "Новый образец"))
        _mil().setdefault(proj.get("category", "ground"), []).append({
            "name": name, "type": proj.get("type", "Модернизированный"), "count": 100, "production": True, "in_service": True,
            "specs": proj.get("specs", ""), "evaluation": proj.get("polygon_report", "Принят по результатам полигонных испытаний."),
            "is_known_globally": False})
        projects.pop(i)
        return f"{name} запущен в серийное производство"
    raise GameError("Неизвестное действие")


def intel_targets() -> list:
    ss = _ss()
    return [c for c in ss.countries if c != ss.player_country]


def intel(country) -> dict:
    targets = intel_targets()
    if country not in targets:
        raise GameError("Нет такой державы для разведки" if targets else "В мире нет других держав")
    mil = _mil(country)
    c = _ss().countries[country]
    categories = {cat: [{"name": str(i.get("name")), "type": str(i.get("type", "")), "count": to_int(i.get("count", 0))}
                        for i in mil.get(cat, []) if i.get("is_known_globally", True)] for cat in CATEGORIES}
    return {"country": country, "targets": targets, "manpower": c.get("stats", {}).get("manpower_approx", "~500 тыс. чел."),
            "categories": categories, "landlocked": country in LANDLOCKED_NATIONS}


def audit(country=None) -> str:
    ss = _ss()
    country = country or ss.player_country
    if country not in ss.countries:
        raise GameError("Такой державы нет")
    cfg = load_config()
    if not cfg.get("api_key"):
        raise GameError("Укажите API-ключ в настройках (телефон)")
    mil = _mil(country)
    audited, err = audit_military_catalog(get_ai_client(cfg["api_key"], cfg["base_url"]), cfg["model_name"], country, mil,
                                          ss.current_date, ss.countries[country].get("stats", {}).get("manpower_approx", "~100 тыс. чел."))
    if err:
        raise GameError(f"Аудит не удался, реестр не изменён: {err}")
    ss.countries[country]["military"] = audited
    return "Реестр упорядочен"
