"""Конвейер обработки хода.

Фаза 1 (параллельно): арбитр, мировой симулятор, дипломатия, ВПК — друг от друга не зависят.
Фаза 2 (параллельно): архитектор (нужны события хода) и ревизор (нужен пакет результатов).
Если упал критичный агент (арбитр/мир) — ход не засчитывается и состояние не меняется.
Результаты проверяются и применяются разом; при любой ошибке состояние откатывается.
"""
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

from ai.agents.architect import agent_geopolitical_architect
from ai.agents.arbiter import agent_internal_arbiter
from ai.agents.auditor import agent_supreme_inspector_auditor
from ai.agents.diplomacy import agent_diplomacy
from ai.agents.vpk import agent_military_industrial_complex
from ai.agents.world import agent_world_simulator
from ai.client import get_ai_client, load_config
from core import world_ops as W
from core.military import CATEGORIES, get_smart_fallback_military
from core.procedural_sim import run_procedural_background_noise
from core.state import (get_scenario_world_context, push_history, restore_snapshot,
                        save_game_to_slot, take_snapshot)
from core.time_system import has_year, is_date_regression

TITLES = {
    "arbiter": "Внутренний арбитр", "world": "Мировой симулятор", "diplomacy": "Дипломатический корпус",
    "vpk": "Министр ВПК", "architect": "Архитектор геополитики", "auditor": "Верховный ревизор",
}
CRITICAL = ("arbiter", "world")


# --------------------------------------------------------------------------- #
# Запуск агентов
# --------------------------------------------------------------------------- #
def _build_state(orders: str) -> dict:
    """Всё, что нужно агентам, берём из session_state здесь, в главном потоке: сами агенты его не читают."""
    ss = st.session_state
    return {
        "turn": ss.turn,
        "current_date": ss.current_date,
        "player_country": ss.player_country,
        "difficulty": ss.difficulty,
        "solar_activity": ss.solar_activity,
        "is_alt_history": ss.get("is_alt_history", False),
        "world_ctx": get_scenario_world_context(),
        "my_country": ss.countries[ss.player_country],
        "countries": ss.countries,
        "rd_projects": ss.rd_projects,
        "ongoing_arcs": list(ss.ongoing_arcs),
        "internal_events": list(ss.internal_events),
        "orders": orders,
    }


def _run_parallel(jobs: dict, workers: int, on_done) -> dict:
    """jobs: {ключ: функция без аргументов -> (dict, tokens)}. Исключение агента превращается в '_error'."""
    def run(key, fn):
        try:
            return key, fn()
        except Exception as e:
            return key, ({"_error": f"{type(e).__name__}: {e}"}, 0)

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(jobs)))) as ex:
        for fut in as_completed([ex.submit(run, k, fn) for k, fn in jobs.items()]):
            key, (res, tokens) = fut.result()
            results[key] = (res, tokens)
            on_done(key, res, tokens)      # st.* вызываем только отсюда, из главного потока
    return results


# --------------------------------------------------------------------------- #
# Применение результатов
# --------------------------------------------------------------------------- #
def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _approved(aud: dict) -> bool:
    v = aud.get("approved", True)
    return v.strip().lower() not in ("false", "no", "нет") if isinstance(v, str) else bool(v)


def _apply_date(world: dict, notes: list):
    ss = st.session_state
    new = world.get("new_date")
    if not isinstance(new, str) or not new.strip():
        notes.append("Мировой симулятор не вернул новую дату — дата не изменилась")
    elif not has_year(new):
        notes.append(f"Дата «{new}» без года отклонена — дата не изменилась")
    elif is_date_regression(ss.current_date, new):
        notes.append(f"Дата «{new}» раньше текущей ({ss.current_date}) — отклонена")
    else:
        ss.current_date = new.strip()


def _apply_diplomacy(dip: dict):
    ss = st.session_state
    me = ss.player_country
    for r in _as_list(dip.get("diplo_responses")):
        if not isinstance(r, dict):
            continue
        a, b = W.resolve_country(r.get("from")), W.resolve_country(r.get("to"))
        text = str(r.get("message") or "").strip()
        if not (a and b and text) or a == b:
            continue
        ss.chats.setdefault(W.chat_key(a, b), []).append({"from": a, "text": text})
        if a != me and b == me:
            ss.unread_messages.add(a)
    for u in _as_list(dip.get("relation_updates")):     # «Отношение к нам» в досье теперь живое
        c = W.resolve_country(u.get("country")) if isinstance(u, dict) else None
        if c and c != me and u.get("stance"):
            ss.countries[c].setdefault("relations", {})[me] = str(u["stance"])[:60]


def _apply_rd(vpk: dict):
    """Обновляем существующие проекты по id/имени. Список целиком больше не подменяется:
    раньше ИИ мог потерять проекты или выдумать новые."""
    projects = st.session_state.rd_projects
    by_id = {p.get("id"): p for p in projects}
    by_name = {str(p.get("name", "")).lower(): p for p in projects}
    for u in _as_list(vpk.get("updated_rd_projects")):
        if not isinstance(u, dict):
            continue
        p = by_id.get(u.get("id")) or by_name.get(str(u.get("name", "")).lower())
        if not p:
            continue
        p["progress"] = max(W.to_int(p.get("progress", 0)), min(100, W.to_int(u.get("progress", 0))))
        for k in ("status", "polygon_report", "target_date", "specs"):
            if u.get(k):
                p[k] = str(u[k])
        p["ready_for_tender"] = bool(u.get("ready_for_tender")) or p["progress"] >= 100


def _apply_production(vpk: dict):
    mil = st.session_state.countries[st.session_state.player_country].get("military")
    if not isinstance(mil, dict):
        return
    index = {str(it.get("name", "")).strip().lower(): it
             for cat in CATEGORIES for it in mil.get(cat, [])
             if it.get("production") and it.get("in_service", True)}
    for inc in _as_list(vpk.get("production_increments")):
        it = index.get(str(inc.get("name", "")).strip().lower()) if isinstance(inc, dict) else None
        if it:   # не больше удвоения парка за ход: страховка от выдуманных миллионов
            it["count"] = W.to_int(it.get("count", 0)) + min(W.to_int(inc.get("added_count", 0)),
                                                              max(50, W.to_int(it.get("count", 0))))


def _apply_transformations(arch: dict, notes: list):
    ss = st.session_state
    me = ss.player_country
    for t in _as_list(arch.get("country_transformations")):
        if not isinstance(t, dict):
            continue
        hide = W.resolve_country(t.get("hide_country"))
        if hide:
            ss.countries[hide]["status"] = "Спящая"
            if hide == me:        # main.py предложит выбрать преемника
                notes.append(f"Держава игрока «{me}» распалась — выберите государство-преемника")
        for sp in _as_list(t.get("spawn_countries")):
            name = str(sp.get("name") or "").strip() if isinstance(sp, dict) else ""
            if not name:
                continue
            if name in ss.countries:                  # раньше перезаписывало существующую страну
                ss.countries[name]["status"] = "Активная"
                continue
            stats = sp.get("stats") if isinstance(sp.get("stats"), dict) else {}
            data = dict(sp, stats={"stability": 60, "war_support": 40, "military_readiness": 50,
                                   "manpower_approx": "~300 тыс. чел.", **stats},
                        military=get_smart_fallback_military(name, ss.current_date),
                        resources="Ограниченные резервы", faction="Нет", overlord=None)
            country = W.new_country(name, data)
            if sp.get("has_civil_war"):
                country["current_issues"].append({"name": "Гражданская война", "start_date": ss.current_date,
                                                  "target_date": "1 Год", "status": "Острая фаза"})
            ss.countries[name] = country
            notes.append(f"Образовано государство «{name}»" + (f" (на месте «{hide}»)" if hide else ""))
            old_k, new_k = W.chat_key(me, hide) if hide else None, W.chat_key(me, name)
            if old_k in ss.chats:
                ss.chats[new_k] = copy.deepcopy(ss.chats[old_k])


def _apply_results(res: dict, orders: str) -> list:
    """Меняет состояние игры. Вызывать только внутри try с откатом по снимку."""
    ss = st.session_state
    notes = []
    arb, world, dip, vpk, arch, aud = (res.get(k) or {} for k in
                                       ("arbiter", "world", "diplomacy", "vpk", "architect", "auditor"))
    patches = aud.get("correction_patches") if isinstance(aud.get("correction_patches"), dict) else {}
    approved = _approved(aud)

    _apply_date(world, notes)

    arcs = [str(a).strip() for a in _as_list(arb.get("updated_ongoing_arcs")) if str(a).strip()]
    if arcs:
        ss.ongoing_arcs = arcs[-25:]

    player_events = W.clean_events(arb.get("new_player_events"))
    if not approved and isinstance(patches.get("add_missing_event"), dict):
        player_events += W.clean_events([patches["add_missing_event"]])
    press = arb.get("press_excerpt")
    press = ({"source": str(press.get("source") or "Пресса"), "quote": str(press["quote"])}
             if isinstance(press, dict) and press.get("quote") else None)

    ss.turn_archives.append({
        "turn": ss.turn + 1,
        "date": ss.current_date,
        "player_orders_raw": orders,
        "world_events": W.clean_events(world.get("new_world_events"), with_date=True),
        "flavor_events": W.clean_events(world.get("flavor_events"), with_date=True),
        "player_events": player_events,
        "press_excerpt": press,
    })

    my_c = ss.countries[ss.player_country]
    stats = W.clean_stats_patch(arb.get("updated_stats"))
    if not approved and patches.get("adjust_stability") is not None:
        stats["stability"] = W.clamp_stat(patches["adjust_stability"], my_c.get("stats", {}).get("stability", 50))
    my_c.setdefault("stats", {}).update(stats)

    if isinstance(arb.get("updated_issues"), list):
        my_c["current_issues"] = [
            {"name": str(i["name"]), "start_date": str(i.get("start_date") or ss.current_date),
             "target_date": str(i.get("target_date") or "Бессрочно"), "status": str(i.get("status") or "Активно")}
            for i in arb["updated_issues"] if isinstance(i, dict) and i.get("name")]

    # Происшествия теперь копятся, пока игрок их не снимет или арбитр не объявит решёнными
    # (раньше список полностью подменялся каждый ход, и кнопка «Снять» теряла смысл).
    resolved = {str(t) for t in _as_list(arb.get("resolved_internal_events"))}
    events = [e for e in ss.internal_events if e.get("title") not in resolved]
    for e in _as_list(arb.get("new_internal_events")):
        if isinstance(e, dict) and e.get("title"):
            events.append({"title": str(e["title"]), "desc": str(e.get("desc") or ""),
                           "type": "negative" if e.get("type") == "negative" else "positive",
                           "impact": str(e.get("impact") or "")})
    ss.internal_events = events[-8:]

    _apply_diplomacy(dip)
    _apply_rd(vpk)
    _apply_production(vpk)
    _apply_transformations(arch, notes)

    run_procedural_background_noise(ss.countries, ss.player_country, ss.turn)
    ss.pending_diplo = []
    ss.turn += 1
    return notes


# --------------------------------------------------------------------------- #
# Точка входа
# --------------------------------------------------------------------------- #
def run_turn(orders_current: str, progress=None) -> dict:
    """Один ход без привязки к интерфейсу. progress(text, kind) вызывается из вызывающего потока.
    Возвращает {"ok": bool, "error": str | None, "audit": str | None, "lines": [...]}."""
    ss = st.session_state
    say = progress or (lambda text, kind="info": None)
    cfg = load_config()
    if not cfg.get("api_key"):
        return {"ok": False, "error": "Укажите API Key в настройках!", "audit": None, "lines": []}

    cl = get_ai_client(cfg["api_key"], cfg["base_url"])
    model, workers = cfg["model_name"], cfg["max_workers"]
    orders = (orders_current or "").strip() or "Нет прямых приказов"
    state = _build_state(orders)
    # ВСЁ, что читает session_state, берём здесь, в главном потоке: из рабочих потоков он недоступен
    alarm = bool(ss.get("alarm_clock_active", False))
    pending = list(ss.pending_diplo)
    recent = [we.get("title", "") for arch in ss.turn_archives[-3:] for we in arch.get("world_events", [])]
    tokens = 0
    res = {}

    def done(key, r, t):
        nonlocal tokens
        tokens += t
        if r.get("_error"):
            say(f"❌ {TITLES[key]}: {r['_error']}", "fail")
        else:
            say(f"✅ {TITLES[key]}", "ok")

    say("Фаза 1/2: арбитр, мировой симулятор, дипломатия и ВПК работают одновременно...", "info")
    phase1 = _run_parallel({
        "arbiter": lambda: agent_internal_arbiter(cl, model, state, orders),
        "world": lambda: agent_world_simulator(cl, model, state, orders, recent, alarm),
        "diplomacy": lambda: agent_diplomacy(cl, model, state, pending),
        "vpk": lambda: agent_military_industrial_complex(cl, model, state, orders),
    }, workers, done)
    res.update({k: v[0] for k, v in phase1.items()})

    broken = [k for k in CRITICAL if res[k].get("_error")]
    if broken:
        return {"ok": False, "audit": None, "lines": [],
                "error": "Не ответили критичные агенты: " + ", ".join(TITLES[k] for k in broken) +
                         ". Состояние игры не изменилось — повторите «Завершить ход»."}

    say("Фаза 2/2: архитектор геополитики и ревизор...", "info")
    state2 = dict(state,
                  turn_world_events=W.clean_events(res["world"].get("new_world_events")),
                  turn_player_events=W.clean_events(res["arbiter"].get("new_player_events")))
    package = {"internal": res["arbiter"], "world": res["world"],
               "vpk": {k: v for k, v in res["vpk"].items() if k != "_error"}}
    phase2 = _run_parallel({
        "architect": lambda: agent_geopolitical_architect(cl, model, state2),
        "auditor": lambda: agent_supreme_inspector_auditor(cl, model, state2, orders, package),
    }, workers, done)
    res.update({k: v[0] for k, v in phase2.items()})

    snapshot = take_snapshot()
    try:
        notes = _apply_results(res, orders)
    except Exception as e:
        restore_snapshot(snapshot)
        return {"ok": False, "audit": None, "lines": [],
                "error": f"Результаты хода не удалось применить, состояние восстановлено: {type(e).__name__}: {e}"}
    push_history(snapshot)
    ss.redo_stack = []          # новый ход начал новую «ветку»: вперёд идти больше некуда

    skipped = [f"{TITLES[k]}: {res[k]['_error']}" for k in TITLES if res.get(k, {}).get("_error")]
    audit_note = res["auditor"].get("audit_notes") if not res["auditor"].get("_error") else None
    ss.token_usage["turn"] = tokens
    ss.token_usage["total"] += tokens
    lines = [f"⚠️ Пропущено из-за сбоя — {s}" for s in skipped] + [f"ℹ️ {n}" for n in notes] \
            + ([f"🔎 Ревизия: {audit_note}"] if audit_note else [])
    ss.last_turn_report = {"turn": ss.turn, "lines": lines}

    if ss.turn % ss.autosave_interval == 0:
        try:
            save_game_to_slot(ss.current_slot)
        except OSError as e:
            ss.last_turn_report["lines"].append(f"⚠️ Автосохранение не удалось: {e}")
    return {"ok": True, "error": None, "audit": audit_note, "lines": ss.last_turn_report["lines"]}


def process_turn_pipeline(orders_current: str):
    """Обёртка для Streamlit-интерфейса."""
    if not load_config().get("api_key"):
        st.error("Укажите API Key в настройках!")
        return
    with st.status("Многоагентный конвейер ИИ обрабатывает ход...", expanded=True) as status:
        result = run_turn(orders_current, progress=lambda text, kind="info": st.write(text))
        if not result["ok"]:
            status.update(label="Ход не обработан", state="error")
            st.error("⚠️ " + result["error"])
            return
        status.update(label=f"Ход обработан! Ревизия: {result['audit'] or 'нет данных'}", state="complete")
    st.rerun()
