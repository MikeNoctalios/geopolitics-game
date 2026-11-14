"""Общие куски промптов для агентов хода. Агенты не трогают st.session_state:
всё нужное приходит в словаре state (их запускают в потоках)."""
import json

from ai.prompts import get_alt_history_directive


def lore(state: dict) -> str:
    return get_alt_history_directive(state.get("is_alt_history", False), state.get("world_ctx", ""))


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def active_country_names(state: dict) -> list:
    return [n for n, c in state["countries"].items() if c.get("status") != "Спящая"]
