"""Дипломатия (двусторонние депеши) и чаты с советниками."""
import json

import streamlit as st

from ai.client import chat_text, get_ai_client, load_config
from ai.prompts import get_alt_history_directive, get_chaos_persona_instructions
from core import world_ops as W
from core.game import GameError
from core.state import get_scenario_world_context

ROLES = {"internal": "Министр внутренних дел", "foreign": "Министр иностранных дел", "defense": "Министр обороны"}
HISTORY_LIMIT = 12


def _ss():
    return st.session_state


def contacts() -> list:
    ss = _ss()
    me, rows = ss.player_country, []
    for name, c in ss.countries.items():
        if name == me:
            continue
        msgs = ss.chats.get(W.chat_key(me, name), [])
        rows.append({"name": name, "great": bool(c.get("is_great_power")), "overlord": c.get("overlord"),
                     "dormant": c.get("status") == "Спящая", "unread": name in ss.unread_messages,
                     "last": (msgs[-1]["text"][:70] if msgs else ""), "count": len(msgs)})
    rows.sort(key=lambda r: (not r["unread"], not r["great"], r["name"]))
    return rows


def chat(country) -> dict:
    ss = _ss()
    if country not in ss.countries or country == ss.player_country:
        raise GameError("Такой державы нет")
    ss.unread_messages.discard(country)
    c, me = ss.countries[country], ss.player_country
    return {"country": country, "messages": list(ss.chats.get(W.chat_key(me, country), [])),
            "pending": sum(1 for d in ss.pending_diplo if d.get("to") == country),
            "dossier": {"region": c.get("region", "Европа"), "regime": c.get("regime", "Неизвестно"),
                        "faction": c.get("faction", "Нет"), "overlord": c.get("overlord"),
                        "stance": (c.get("relations") or {}).get(me, "Нейтральное"),
                        "ambitions": c.get("ambitions", "Неизвестно"), "fears": c.get("fears", "Неизвестно"),
                        "manpower": c.get("stats", {}).get("manpower_approx", "~500 тыс. чел.")}}


def send(country, text):
    ss = _ss()
    text = str(text or "").strip()[:4000]
    if country not in ss.countries or country == ss.player_country:
        raise GameError("Такой державы нет")
    if not text:
        raise GameError("Пустая депеша")
    me = ss.player_country
    ss.chats.setdefault(W.chat_key(me, country), []).append({"from": me, "text": text})
    ss.pending_diplo.append({"from": me, "to": country, "text": text})   # ответ придёт с завершением хода


def advisor_chat(role) -> list:
    if role not in ROLES:
        raise GameError("Нет такого министра")
    return list(_ss().advisor_chats[role])


def advisor_send(role, text) -> list:
    ss, cfg = _ss(), load_config()
    if role not in ROLES:
        raise GameError("Нет такого министра")
    text = str(text or "").strip()[:4000]
    if not text:
        raise GameError("Пустой вопрос")
    if not cfg.get("api_key"):
        raise GameError("Укажите API-ключ в настройках (телефон)")
    chat_ = ss.advisor_chats[role]
    me = ss.countries[ss.player_country].get("stats", {})
    lore = get_alt_history_directive(ss.get("is_alt_history", False), get_scenario_world_context())
    system = f"""You are the {ROLES[role]} of {ss.player_country}.
{lore}
{get_chaos_persona_instructions(ss.solar_activity)}
Respond STRICTLY in fluent Russian (1-2 paragraphs).
Date: {ss.current_date}.
Stability: {me.get('stability')}, War support: {me.get('war_support')}, Readiness: {me.get('military_readiness')}.
Active Arcs: {json.dumps(ss.ongoing_arcs, ensure_ascii=False)}."""
    messages = [{"role": "system", "content": system}] + chat_[-(HISTORY_LIMIT - 1):] + [{"role": "user", "content": text}]
    reply, tokens, err = chat_text(get_ai_client(cfg["api_key"], cfg["base_url"]), cfg["model_name"], messages, temperature=0.7)
    if not reply:
        raise GameError(f"Министр не смог ответить: {err}")      # реплика игрока не фиксируется — её можно отправить снова
    chat_.append({"role": "user", "content": text})
    chat_.append({"role": "assistant", "content": reply})
    ss.token_usage["total"] += tokens
    return list(chat_)
