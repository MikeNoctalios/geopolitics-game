"""Контроллер игры: то, что раньше было вшито в виджеты Streamlit. Возвращает только JSON-совместимые данные.

Используется веб-интерфейсом «стол» (server.py); старый Streamlit-интерфейс берёт отсюда start_new_game_session.
"""
import json
import os
import threading

import streamlit as st

from ai.agents.gm import agent_gm_orchestrator
from ai.client import get_ai_client, load_config, save_config, test_connection
from ai.pipeline import run_turn
from core import state as S
from core import world_ops as W
from core.commands import execute_command_pipeline
from core.military import ensure_military_loaded
from core.time_system import extract_year

SLOT_IDS = (1, 2, 3)
DIFFICULTIES = ("Шутка", "Лёгкий", "Нормальный", "Хардкор")


from core.errors import GameError  # noqa: E402,F401  (имя остаётся доступным как G.GameError)


def _ss():
    return st.session_state


# --------------------------------------------------------------------------- #
# Меню: слоты и сценарии
# --------------------------------------------------------------------------- #
def list_slots() -> list:
    return [{"id": i, **S.get_slot_info(i)} for i in SLOT_IDS]


def _read_scenario(file: str) -> dict:
    if os.sep in file or "/" in file or not file.endswith(".json"):
        raise GameError("Недопустимое имя сценария")
    with open(os.path.join(S.SCENARIOS_DIR, file), "r", encoding="utf-8") as f:
        return json.load(f)


def list_scenarios() -> list:
    out = []
    for sf in os.listdir(S.SCENARIOS_DIR):
        if not sf.endswith(".json"):
            continue
        try:
            sd = _read_scenario(sf)
        except (OSError, ValueError):
            continue
        has_ctx = bool(sd.get("world_context") or sd.get("world_context_file"))
        out.append({
            "file": sf, "name": sd.get("name", sf), "description": sd.get("description", ""),
            "start_date": sd.get("start_date", "1935"), "year": extract_year(sd.get("start_date", "1935")),
            "count": len(sd.get("countries", {})), "is_alt_history": sd.get("is_alt_history", has_ctx),
        })
    out.sort(key=lambda x: (x["year"], x["name"]))
    return out


def scenario_countries(file: str) -> list:
    countries = _read_scenario(file).get("countries", {})
    rows = []
    for name, d in countries.items():
        stats = d.get("stats", {}) if isinstance(d.get("stats"), dict) else {}
        rows.append({
            "name": name, "is_great_power": bool(d.get("is_great_power")), "region": d.get("region", "Европа"),
            "regime": d.get("regime", ""), "faction": d.get("faction", "Нет"), "profile": d.get("profile", ""),
            "ambitions": d.get("ambitions", ""), "fears": d.get("fears", ""), "resources": d.get("resources", ""),
            "stability": stats.get("stability", 0), "war_support": stats.get("war_support", 0),
            "military_readiness": stats.get("military_readiness", 0), "manpower": stats.get("manpower_approx", "?"),
        })
    rows.sort(key=lambda r: (not r["is_great_power"], r["name"]))
    return rows


def start_new_game_session(slot_id, scenario_file, country, difficulty, solar_activity, is_alt_history):
    scen = _read_scenario(scenario_file)
    if country not in scen.get("countries", {}):
        raise ValueError(f"В сценарии нет державы «{country}»")
    ss = _ss()
    ss.clear()
    S.init_session_state()          # значения по умолчанию (чаты, заметки, советники, история...)
    ss.in_game = True
    ss.current_slot = slot_id
    ss.scenario_file = scenario_file
    ss.scenario_name = scen.get("name", scenario_file)
    ss.turn = 1
    ss.current_date = scen.get("start_date", "1 Января 1935")
    ss.player_country = country
    ss.difficulty = difficulty
    ss.solar_activity = solar_activity
    ss.is_alt_history = is_alt_history
    ss.alarm_clock_active = False
    ss.ongoing_arcs = [f"Начало кампании {ss.current_date}"]
    ss.turn_archives = [{
        "turn": 1, "date": ss.current_date, "player_orders_raw": "Старт сценария",
        "world_events": scen.get("world_events", []), "flavor_events": [], "player_events": [], "press_excerpt": None,
    }]
    ss.countries = scen["countries"]
    ss.countries[country]["status"] = "Активная"
    S.migrate_loaded_state()        # типы статов/вооружений, пометка «реестр не создан»
    ensure_military_loaded(country)
    S.save_game_to_slot(slot_id)


def start_new_game(slot_id, scenario_file, country, difficulty, solar):
    if int(slot_id) not in SLOT_IDS:
        raise GameError("Нет такой ячейки сохранения")
    if difficulty not in DIFFICULTIES:
        raise GameError("Неизвестный уровень сложности")
    is_alt = next((s["is_alt_history"] for s in list_scenarios() if s["file"] == scenario_file), False)
    try:
        start_new_game_session(int(slot_id), scenario_file, country, difficulty, max(0, min(10, int(solar))), is_alt)
    except (ValueError, OSError) as e:
        raise GameError(f"Не удалось начать кампанию: {e}")


def load_slot(slot_id):
    try:
        S.load_game_from_slot(int(slot_id))
    except (ValueError, OSError) as e:
        raise GameError(f"Сохранение не загрузилось: {e}")


def delete_slot(slot_id):
    S.delete_slot(int(slot_id))


def slot_file(slot_id) -> str:
    with open(S.get_slot_path(int(slot_id)), "r", encoding="utf-8") as f:
        return f.read()


def import_slot(slot_id, data):
    problem = S.validate_save(data)
    if problem:
        raise GameError(f"Файл не подходит: {problem}")
    if S.get_slot_info(int(slot_id)).get("exists"):
        raise GameError("Ячейка занята — сначала удалите её")
    with open(S.get_slot_path(int(slot_id)), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# Игра: фаза, шапка, повестка
# --------------------------------------------------------------------------- #
def phase() -> str:
    ss = _ss()
    if not ss.get("in_game"):
        return "menu"
    me = ss.countries.get(ss.player_country)
    return "successor" if me is None or me.get("status") == "Спящая" else "game"


def hud() -> dict:
    ss = _ss()
    me = ss.countries.get(ss.player_country) or {}
    stats = me.get("stats", {})
    return {
        "country": ss.player_country, "date": ss.current_date, "turn": ss.turn, "difficulty": ss.difficulty,
        "solar": ss.solar_activity, "slot": ss.current_slot, "scenario": ss.get("scenario_name", ""),
        "stats": {k: stats.get(k, 0) for k in W.STAT_KEYS}, "manpower": stats.get("manpower_approx", "?"),
        "unread": sorted(ss.unread_messages), "tokens": dict(ss.token_usage),
        "alarm": bool(ss.alarm_clock_active), "autosave_interval": ss.autosave_interval,
        "can_rollback": len(ss.history), "can_redo": len(ss.get("redo_stack", [])),
    }


def successor_candidates() -> list:
    cs = _ss().countries
    alive = [c for c, d in cs.items() if d.get("status") != "Спящая"]
    return alive or list(cs)


def choose_successor(name):
    cs = _ss().countries
    if name not in cs:
        raise GameError("Такой державы нет на карте")
    _ss().player_country = name
    cs[name]["status"] = "Активная"
    ensure_military_loaded(name)


def agenda() -> dict:
    ss = _ss()
    me = ss.countries[ss.player_country]
    return {
        "issues": [dict(i) for i in me.get("current_issues", [])],
        "events": [dict(e, index=i) for i, e in enumerate(ss.internal_events)],
    }


def dismiss_event(index):
    ev = _ss().internal_events
    if 0 <= int(index) < len(ev):
        ev.pop(int(index))


def get_orders() -> str:
    return _ss().get(f"orders_{_ss().turn}", "")


def set_orders(text):
    _ss()[f"orders_{_ss().turn}"] = str(text)[:20000]


def end_turn_warnings() -> list:
    ss, out = _ss(), []
    if ss.unread_messages:
        out.append(f"Непрочитанные депеши от: {', '.join(sorted(ss.unread_messages))}")
    if not get_orders().strip():
        out.append("Вы не отдали никаких приказов на текущий ход")
    if any(e.get("type") == "negative" for e in ss.internal_events):
        out.append("В стране действуют активные негативные происшествия!")
    return out


# --------------------------------------------------------------------------- #
# Газета
# --------------------------------------------------------------------------- #
def news_index() -> list:
    return [{"turn": a.get("turn"), "date": a.get("date")} for a in _ss().turn_archives]


def news(turn=None) -> dict:
    archives = _ss().turn_archives
    arch = next((a for a in archives if a.get("turn") == turn), None) if turn is not None else None
    arch = arch or archives[-1]
    press = arch.get("press_excerpt")
    return {
        "turn": arch.get("turn"), "date": arch.get("date"), "is_current": arch is archives[-1],
        "orders": arch.get("player_orders_raw", ""),
        "world": arch.get("world_events", []), "flavor": arch.get("flavor_events", []),
        "ours": arch.get("player_events", []),
        "press": press if isinstance(press, dict) else ({"source": "Пресса", "quote": str(press)} if press else None),
    }


# --------------------------------------------------------------------------- #
# Блокнот
# --------------------------------------------------------------------------- #
NOTE_PAGES = 99


def notes() -> dict:
    ss = _ss()
    titles = ss.setdefault("notes_titles", {})
    return {"pages": {k: {"text": v, "title": titles.get(k, "")} for k, v in ss.notes_pages.items() if v or titles.get(k)},
            "count": NOTE_PAGES}


def note_set(page, text=None, title=None):
    ss = _ss()
    key = str(int(page))
    if not 1 <= int(key) <= NOTE_PAGES:
        raise GameError("Нет такой страницы")
    if text is not None:
        ss.notes_pages[key] = str(text)[:50000]
    if title is not None:
        ss.setdefault("notes_titles", {})[key] = str(title)[:60]


# --------------------------------------------------------------------------- #
# Телефон: Гейммастер, настройки, откат, выход
# --------------------------------------------------------------------------- #
def gm_send(text):
    ss, cfg = _ss(), load_config()
    ss.gm_chat.append({"role": "user", "content": str(text)})
    if not cfg.get("api_key"):
        ss.gm_chat.append({"role": "assistant", "content": "⚠️ Не указан API-ключ (Настройки на телефоне)."})
        return
    try:
        cl = get_ai_client(cfg["api_key"], cfg["base_url"])
        gm_res, t_count = agent_gm_orchestrator(cl, cfg["model_name"], text, {
            "player_country": ss.player_country, "countries": ss.countries, "current_date": ss.current_date,
            "turn": ss.turn, "is_alt_history": ss.get("is_alt_history", False)})
        ss.token_usage["total"] += t_count
        if gm_res.get("_error"):    # раньше сбой выглядел как «Указание принято»
            ss.gm_chat.append({"role": "assistant", "content": f"⚠️ ИИ не ответил, ничего не изменено: {gm_res['_error']}"})
            return
        ss.gm_chat.append({"role": "assistant", "content": gm_res.get("confirmation_message", "Команды приведены в исполнение.")})
        for line in execute_command_pipeline(gm_res.get("commands", [])):
            ss.gm_chat.append({"role": "assistant", "content": line})
    except Exception as e:
        ss.gm_chat.append({"role": "assistant", "content": f"Ошибка исполнения: {type(e).__name__}: {e}"})


def config_public() -> dict:
    cfg = load_config()
    key = cfg.get("api_key", "")
    return {"has_key": bool(key), "key_tail": key[-4:] if len(key) > 8 else "", "base_url": cfg.get("base_url", ""),
            "model_name": cfg.get("model_name", ""), "theme": cfg.get("theme", ""),
            "json_mode": bool(cfg.get("json_mode")), "max_workers": cfg.get("max_workers", 4)}


def config_update(api_key=None, base_url=None, model_name=None, theme=None):
    cfg = load_config()
    save_config(api_key if api_key else cfg["api_key"],      # пустое поле = оставить прежний ключ
                cfg["base_url"] if base_url is None else base_url,
                cfg["model_name"] if model_name is None else model_name,
                cfg.get("theme", "") if theme is None else theme)


def config_test() -> dict:
    ok, msg = test_connection(load_config())
    return {"ok": ok, "message": msg}


def set_autosave(n):
    _ss().autosave_interval = max(1, min(50, int(n)))


def set_alarm(on):
    _ss().alarm_clock_active = bool(on)


def rollback() -> bool:
    ok = S.request_rollback()
    if ok:
        S.apply_pending_rollback()
    return ok


def redo() -> bool:
    ok = S.request_redo()
    if ok:
        S.apply_pending_rollback()
    return ok


def save_now():
    S.save_game_to_slot(_ss().current_slot)


def exit_to_menu():
    save_now()
    _ss().in_game = False


# --------------------------------------------------------------------------- #
# Ход в фоновом потоке (интерфейс опрашивает статус)
# --------------------------------------------------------------------------- #
class TurnJob:
    def __init__(self):
        self._lock = threading.Lock()
        self._reset()

    def _reset(self):
        self.running, self.lines, self.result = False, [], None

    def start(self) -> bool:
        with self._lock:
            if self.running:
                return False
            self.running, self.lines, self.result = True, [], None
        threading.Thread(target=self._work, args=(get_orders(),), daemon=True).start()
        return True

    def _work(self, orders):
        try:
            result = run_turn(orders, progress=lambda text, kind="info": self.lines.append({"text": text, "kind": kind}))
        except Exception as e:      # на всякий случай: поток не должен умереть молча
            result = {"ok": False, "error": f"{type(e).__name__}: {e}", "audit": None, "lines": []}
        self.result, self.running = result, False

    def status(self) -> dict:
        return {"running": self.running, "lines": list(self.lines), "result": self.result}


TURN = TurnJob()
