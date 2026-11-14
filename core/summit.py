"""Международные саммиты: создание, прения, голосование, демарш, итоги."""
import streamlit as st

from ai.agents.conference import (agent_conference_foreign_minister_advice, agent_simulate_conference_round,
                                  agent_simulate_conference_voting, agent_simulate_conference_walkout)
from ai.client import get_ai_client, load_config
from core import world_ops as W
from core.game import GameError


def _ss():
    return st.session_state


def _env():
    cfg = load_config()
    if not cfg.get("api_key"):
        raise GameError("Укажите API-ключ в настройках (телефон)")
    ss = _ss()
    return get_ai_client(cfg["api_key"], cfg["base_url"]), cfg["model_name"], ss.player_country, ss.difficulty, ss.solar_activity


def _active():
    conf = _ss().get("active_conference")
    if not conf:
        raise GameError("Саммит не созван")
    return conf


def state() -> dict:
    ss = _ss()
    me = ss.player_country
    return {"player": me, "active": ss.get("active_conference"), "archive": list(ss.conference_archives),
            "nations": [{"name": n, "great": bool(c.get("is_great_power"))} for n, c in ss.countries.items() if n != me],
            "advice": ss.get("temp_fm_summit_advice", "")}


def create(title, topic, participants, secrecy):
    ss = _ss()
    if ss.get("active_conference"):
        raise GameError("Уже идёт другой саммит")
    parts = [p for p in dict.fromkeys(participants or []) if p in ss.countries and p != ss.player_country]
    if not parts:
        raise GameError("Нужно пригласить хотя бы одну державу")
    sec = "Только участники (Секретно)" if "Секрет" in str(secrecy) or "участники" in str(secrecy) else "Все (Публичный саммит)"
    ss.active_conference = W.new_conference(str(title or "Международный саммит")[:120], ss.player_country, parts,
                                            str(topic or "Урегулирование кризиса")[:1000], sec)
    ss.temp_fm_summit_advice = ""


def speak(text):
    conf = _active()
    if conf["stage"] != "discussion":
        raise GameError("Прения закончены")
    client, model, me, diff, solar = _env()
    text = str(text or "").strip()[:2000]
    res, tokens = agent_simulate_conference_round(client, model, conf, me, text or None, diff, solar)
    _ss().token_usage["total"] += tokens
    if res.get("_error"):
        raise GameError(f"Делегаты не ответили (реплика не засчитана): {res['_error']}")
    conf["dialogue"].append({"speaker": me, "text": text or "(Воздержался от комментариев)"})
    conf["dialogue"].extend(res["statements"])


def propose(text):
    conf = _active()
    if conf["stage"] != "discussion":
        raise GameError("Голосование уже идёт")
    conf["final_proposal"] = str(text or conf["topic"]).strip()[:2000]
    conf["stage"] = "voting"


def vote(choice):
    conf = _active()
    if conf["stage"] != "voting":
        raise GameError("Сейчас не голосование")
    if choice not in ("За", "Против", "Воздержался"):
        raise GameError("Недопустимый голос")
    client, model, me, diff, solar = _env()
    res, tokens = agent_simulate_conference_voting(client, model, conf, conf.get("final_proposal") or conf["topic"], me, choice, diff, solar)
    _ss().token_usage["total"] += tokens
    if res.get("_error"):
        raise GameError(f"Голосование не состоялось, попробуйте ещё раз: {res['_error']}")
    conf["votes"] = res["votes"]
    conf["votes"][me] = {"vote": choice, "reason": "Голос суверена."}
    conf["passed"] = res["resolution_passed"]
    conf["summary"] = res.get("outcome_summary", "Резолюция рассмотрена.")
    conf["positions_summary"] = res.get("positions_summary", "Позиции участников зафиксированы.")
    conf["minister_debrief"] = res.get("minister_debrief", "МИД зафиксировал итоги голосования.")
    conf["stage"] = "concluded"


def walkout():
    conf = _active()
    if conf["stage"] == "concluded":
        raise GameError("Саммит уже завершён голосованием")
    client, model, me, diff, solar = _env()
    res, tokens = agent_simulate_conference_walkout(client, model, conf, me, diff, solar)
    ss = _ss()
    ss.token_usage["total"] += tokens
    if res.get("_error"):
        raise GameError(f"Не удалось смоделировать реакцию, вы остаётесь на саммите: {res['_error']}")
    conf["status"] = "Сорван демаршем игрока"
    conf["summary"] = f"Демарш державы {me}. {res.get('walkout_reaction_summary', '')} Принято за закрытыми дверями: {res.get('closed_door_resolution', '')}"
    conf["minister_debrief"] = res.get("minister_debrief", "МИД зафиксировал охлаждение отношений.")
    conf["positions_summary"] = "Державы завершили заседание в узком кругу после ухода нашей делегации."
    conf["dialogue"].extend(res["closing_dialogue"])
    W.add_arc(f"Демарш на саммите «{conf['title']}»: {conf['summary']}")
    W.add_world_event(f"Скандал на саммите: {conf['title']}", conf["summary"])
    ss.conference_archives.append(conf)
    ss.active_conference = None


def advice() -> str:
    conf = _active()
    client, model, me, diff, solar = _env()
    text, tokens = agent_conference_foreign_minister_advice(client, model, conf, me, diff, solar)
    ss = _ss()
    ss.token_usage["total"] += tokens
    ss.temp_fm_summit_advice = text
    return text


def close():
    conf = _active()
    if conf["stage"] != "concluded":
        raise GameError("Сначала закончите голосование или совершите демарш")
    conf["status"] = "Принята" if conf.get("passed") else "Отклонена"
    if conf.get("passed"):
        W.add_arc(f"Итоги саммита «{conf['title']}»: {conf.get('summary')}")
        W.add_world_event(f"Итоги саммита: {conf['title']}", f"Принята резолюция: {conf.get('summary')}")
    ss = _ss()
    ss.conference_archives.append(conf)
    ss.active_conference = None
