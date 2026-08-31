import os
import json
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVES_DIR = os.path.join(BASE_DIR, "saves")
SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios")

for d in [SAVES_DIR, SCENARIOS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

GAME_STATE_KEYS = {
    "in_game", "current_slot", "scenario_file", "scenario_name", "turn", "current_date", 
    "player_country", "difficulty", "solar_activity", "is_alt_history", "alarm_clock_active", 
    "turn_archives", "countries", "chats", "unread_messages", "internal_events", 
    "military_mod_requests", "rd_projects", "advisor_chats", "notes_pages", "note_page_num", 
    "pending_diplo", "gm_chat", "token_usage", "autosave_interval", "ongoing_arcs",
    "diplo_target_country", "active_conference", "conference_archives"
}

def init_session_state():
    if "unread_messages" not in st.session_state: st.session_state.unread_messages = set()
    if "history" not in st.session_state: st.session_state.history = []
    if "pending_diplo" not in st.session_state: st.session_state.pending_diplo = []
    if "internal_events" not in st.session_state: st.session_state.internal_events = []
    if "military_mod_requests" not in st.session_state: st.session_state.military_mod_requests = []
    if "rd_projects" not in st.session_state: st.session_state.rd_projects = []
    if "token_usage" not in st.session_state: st.session_state.token_usage = {"turn": 0, "total": 0}
    if "autosave_interval" not in st.session_state: st.session_state.autosave_interval = 3
    if "gm_chat" not in st.session_state: st.session_state.gm_chat = []
    if "notes_pages" not in st.session_state: st.session_state.notes_pages = {str(i): "" for i in range(1, 100)}
    if "note_page_num" not in st.session_state: st.session_state.note_page_num = 1
    if "ongoing_arcs" not in st.session_state: st.session_state.ongoing_arcs = []
    if "alarm_clock_active" not in st.session_state: st.session_state.alarm_clock_active = False
    if "active_conference" not in st.session_state: st.session_state.active_conference = None
    if "conference_archives" not in st.session_state: st.session_state.conference_archives = []

def get_slot_path(slot_id):
    return os.path.join(SAVES_DIR, f"slot_{slot_id}.json")

def get_slot_info(slot_id):
    path = get_slot_path(slot_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
                return {
                    "exists": True,
                    "country": d.get("player_country", "Неизвестно"),
                    "turn": d.get("turn", 1),
                    "date": d.get("current_date", "1935"),
                    "difficulty": d.get("difficulty", "Нормальный"),
                    "solar": d.get("solar_activity", 1)
                }
        except Exception:
            return {"exists": False, "corrupted": True}
    return {"exists": False}

def save_game_to_slot(slot_id):
    path = get_slot_path(slot_id)
    save_data = {}
    for k in GAME_STATE_KEYS:
        if k in st.session_state:
            v = st.session_state[k]
            save_data[k] = list(v) if isinstance(v, set) else v
    with open(path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

def load_game_from_slot(slot_id):
    path = get_slot_path(slot_id)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for k in GAME_STATE_KEYS:
        if k in data:
            st.session_state[k] = data[k]
            
    if "unread_messages" in st.session_state and isinstance(st.session_state.unread_messages, list):
        st.session_state.unread_messages = set(st.session_state.unread_messages)
    init_session_state()
    st.session_state.current_slot = slot_id
    st.session_state.in_game = True

def delete_slot(slot_id):
    path = get_slot_path(slot_id)
    if os.path.exists(path):
        os.remove(path)

def get_scenario_world_context() -> str:
    scen_file = st.session_state.get("scenario_file")
    if not scen_file: return ""
    scen_path = os.path.join(SCENARIOS_DIR, scen_file)
    if not os.path.exists(scen_path): return ""
    try:
        with open(scen_path, "r", encoding="utf-8") as f:
            scen_d = json.load(f)
        ctx = scen_d.get("world_context") or scen_d.get("world_context_file")
        if not ctx: return ""
        if isinstance(ctx, str) and (ctx.endswith(".txt") or os.path.exists(os.path.join(SCENARIOS_DIR, ctx))):
            txt_path = os.path.join(SCENARIOS_DIR, ctx)
            if os.path.exists(txt_path):
                with open(txt_path, "r", encoding="utf-8") as tf:
                    return tf.read().strip()
        return str(ctx).strip()
    except Exception:
        return ""