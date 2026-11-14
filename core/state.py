"""Состояние игры: значения по умолчанию, сохранения, откат ходов."""
import copy
import json
import os

import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVES_DIR = os.path.join(BASE_DIR, "saves")
SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios")
os.makedirs(SAVES_DIR, exist_ok=True)
os.makedirs(SCENARIOS_DIR, exist_ok=True)

# Что попадает в файл сохранения.
GAME_STATE_KEYS = {
    "in_game", "current_slot", "scenario_file", "scenario_name", "turn", "current_date",
    "player_country", "difficulty", "solar_activity", "is_alt_history", "alarm_clock_active",
    "turn_archives", "countries", "chats", "unread_messages", "internal_events",
    "rd_projects", "advisor_chats", "notes_pages", "notes_titles", "note_page_num",
    "pending_diplo", "gm_chat", "token_usage", "autosave_interval", "ongoing_arcs",
    "diplo_target_country", "active_conference", "conference_archives",
}

# Что откатывается кнопкой «Откатить ход». Заметки, чаты с советниками, счётчики токенов
# и настройки откатывать не нужно (раньше откат стирал и заметки игрока).
ROLLBACK_KEYS = {
    "turn", "current_date", "player_country", "alarm_clock_active", "turn_archives", "countries",
    "chats", "unread_messages", "internal_events", "rd_projects", "pending_diplo",
    "ongoing_arcs", "diplo_target_country", "active_conference", "conference_archives",
}
MAX_HISTORY = 5   # снимков для отката (раньше росли бесконечно, по полной копии мира)

ADVISOR_GREETINGS = {
    "internal": "Господин, внутренний порядок, законы и стабильность на моем контроле.",
    "foreign": "Внешнеполитическое ведомство готово к защите интересов державы.",
    "defense": "Генеральный штаб на связи. Докладываю о готовности армии и флота.",
}


def default_advisor_chats() -> dict:
    return {k: [{"role": "assistant", "content": v}] for k, v in ADVISOR_GREETINGS.items()}


def _defaults() -> dict:
    return {
        "history": [],
        "redo_stack": [],
        "unread_messages": set(),
        "pending_diplo": [],
        "internal_events": [],
        "rd_projects": [],
        "turn_archives": [],
        "countries": {},
        "chats": {},
        "token_usage": {"turn": 0, "total": 0},
        "autosave_interval": 3,
        "gm_chat": [],
        "notes_pages": {str(i): "" for i in range(1, 100)},
        "note_page_num": 1,
        "notes_titles": {},
        "ongoing_arcs": [],
        "alarm_clock_active": False,
        "active_conference": None,
        "conference_archives": [],
        "advisor_chats": default_advisor_chats(),
    }


def init_session_state():
    """Вызывается в начале каждого прогона app.py. Заодно применяет отложенный откат хода."""
    for k, v in _defaults().items():
        if k not in st.session_state:
            st.session_state[k] = v
    apply_pending_rollback()


# --------------------------------------------------------------------------- #
# Откат хода
# --------------------------------------------------------------------------- #
def take_snapshot() -> dict:
    return {k: copy.deepcopy(st.session_state[k]) for k in ROLLBACK_KEYS if k in st.session_state}


def restore_snapshot(snap: dict):
    for k, v in snap.items():
        st.session_state[k] = copy.deepcopy(v)


def push_history(snap: dict):
    hist = st.session_state.setdefault("history", [])
    hist.append(snap)
    del hist[:-MAX_HISTORY]


def request_rollback() -> bool:
    """Назад на ход. Нынешнее состояние кладётся в redo_stack, чтобы можно было вернуться вперёд."""
    ss = st.session_state
    if not ss.get("history"):
        return False
    stack = ss.setdefault("redo_stack", [])
    stack.append(take_snapshot())
    del stack[:-MAX_HISTORY]
    ss.pending_rollback = ss.history.pop()
    return True


def request_redo() -> bool:
    """Вперёд на ход (отмена отката). Возможно, пока не сыгран новый ход."""
    ss = st.session_state
    if not ss.get("redo_stack"):
        return False
    push_history(take_snapshot())
    ss.pending_rollback = ss.redo_stack.pop()
    return True


def apply_pending_rollback() -> bool:
    """Кнопка в сайдбаре лишь ставит флаг pending_rollback; применяем его до создания виджетов.
    Вызывается из main.py (там же сохраняется слот) и, на всякий случай, из init_session_state()."""
    snap = st.session_state.pop("pending_rollback", None)
    if isinstance(snap, dict):
        restore_snapshot(snap)
        return True
    return False


# --------------------------------------------------------------------------- #
# Сохранения
# --------------------------------------------------------------------------- #
def get_slot_path(slot_id):
    return os.path.join(SAVES_DIR, f"slot_{slot_id}.json")


def get_slot_info(slot_id):
    path = get_slot_path(slot_id)
    if not os.path.exists(path):
        return {"exists": False}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {
            "exists": True,
            "country": d.get("player_country", "Неизвестно"),
            "turn": d.get("turn", 1),
            "date": d.get("current_date", "1935"),
            "difficulty": d.get("difficulty", "Нормальный"),
            "solar": d.get("solar_activity", 1),
        }
    except (OSError, ValueError, AttributeError):
        return {"exists": False, "corrupted": True}


def _json_default(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"{type(o).__name__} не сериализуется в JSON")


def save_game_to_slot(slot_id):
    save_data = {k: st.session_state[k] for k in GAME_STATE_KEYS if k in st.session_state}
    path = get_slot_path(slot_id)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:       # пишем во временный файл: обрыв не убьёт старое сохранение
        json.dump(save_data, f, ensure_ascii=False, indent=2, default=_json_default)
    os.replace(tmp, path)


def validate_save(data) -> str:
    """'' если файл похож на сохранение, иначе текст причины."""
    if not isinstance(data, dict):
        return "это не файл сохранения (ожидался JSON-объект)"
    if not isinstance(data.get("countries"), dict) or not data["countries"]:
        return "в файле нет списка государств"
    if data.get("player_country") not in data["countries"]:
        return "страна игрока отсутствует в списке государств"
    return ""


def migrate_loaded_state():
    """Приводит сохранения старых версий к текущим структурам."""
    from core.military import clean_catalog, is_pending   # импорт здесь: military зависит от state
    from core.world_ops import clamp_stat
    ss = st.session_state
    for c in ss.countries.values():
        if not isinstance(c, dict):
            continue
        c["military"] = None if is_pending(c.get("military")) else clean_catalog(c["military"])
        stats = c.setdefault("stats", {})
        for k in ("stability", "war_support", "military_readiness"):
            stats[k] = clamp_stat(stats.get(k), 50)
        stats.setdefault("manpower_approx", "~100 тыс. чел.")
        c.setdefault("current_issues", [])
        c.setdefault("relations", {})
    ss.unread_messages = set(ss.unread_messages)
    for role, greeting in default_advisor_chats().items():
        ss.advisor_chats.setdefault(role, greeting)


def load_game_from_slot(slot_id):
    with open(get_slot_path(slot_id), "r", encoding="utf-8") as f:
        data = json.load(f)
    problem = validate_save(data)
    if problem:
        raise ValueError(problem)
    for k in GAME_STATE_KEYS:          # сначала чистим хвосты прошлой партии
        st.session_state.pop(k, None)
    st.session_state.history = []
    for k in GAME_STATE_KEYS:
        if k in data:
            st.session_state[k] = data[k]
    init_session_state()
    migrate_loaded_state()
    st.session_state.current_slot = slot_id
    st.session_state.in_game = True


def delete_slot(slot_id):
    path = get_slot_path(slot_id)
    if os.path.exists(path):
        os.remove(path)


def get_scenario_world_context() -> str:
    scen_file = st.session_state.get("scenario_file")
    if not scen_file:
        return ""
    scen_path = os.path.join(SCENARIOS_DIR, scen_file)
    try:
        with open(scen_path, "r", encoding="utf-8") as f:
            scen_d = json.load(f)
        ctx = scen_d.get("world_context") or scen_d.get("world_context_file")
        if not ctx:
            return ""
        if isinstance(ctx, str) and (ctx.endswith(".txt") or os.path.exists(os.path.join(SCENARIOS_DIR, ctx))):
            txt_path = os.path.join(SCENARIOS_DIR, ctx)
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8") as tf:
                    return tf.read().strip()
        return str(ctx).strip()
    except (OSError, ValueError, AttributeError):
        return ""
