"""Саммиты. Вызываются из UI (главный поток), поэтому здесь можно читать st.session_state."""
import streamlit as st

from ai.agents._common import dumps
from ai.client import call_json, chat_text
from ai.prompts import get_alt_history_directive, get_chaos_persona_instructions, get_difficulty_directive
from core.state import get_scenario_world_context

SWISS = "Швейцария"
SWISS_LINE = "Я бот и мне нечего сказать!"


def _header(difficulty, solar_activity) -> str:
    lore = get_alt_history_directive(st.session_state.get("is_alt_history", False), get_scenario_world_context())
    return f"{lore}\n    {get_difficulty_directive(difficulty)}\n    {get_chaos_persona_instructions(solar_activity)}"


def _transcript(conf: dict, n: int = 10) -> str:
    return dumps(conf.get("dialogue", [])[-n:])


def agent_simulate_conference_round(client, model, conference_data: dict, player_country: str,
                                    player_speech: str, difficulty: str, solar_activity: int):
    participants = conference_data.get("participants", [])
    speakers = [p for p in participants if p != player_country]
    prompt = f"""
    You are the MULTILATERAL SUMMIT DIPLOMATIC ENGINE.
    {_header(difficulty, solar_activity)}
    Summit: "{conference_data.get('title')}".
    Agenda: "{conference_data.get('topic', 'Международный кризис')}".
    Participants: {dumps(participants)}.
    Previous Dialogue: {_transcript(conference_data)}.
    Player ({player_country}) Statement: "{player_speech if player_speech else '(Player remained silent)'}".

    Each of these delegations speaks once, in its own interest: {dumps(speakers)}.
    NEVER write lines for {player_country} — that is the human player.
    SWITZERLAND RULE (easter egg): if "{SWISS}" participates, first decide whether the agenda or the debate directly concerns Switzerland (its territory, neutrality, banks, borders, citizens) and report it in "switzerland_concerned". If it is NOT concerned, its text MUST BE EXACTLY: "{SWISS_LINE}". If it IS concerned, it speaks normally in character.

    Return STRICTLY valid JSON:
    {{
      "switzerland_concerned": bool,
      "statements": [
         {{"speaker": "<Country Name>", "text": "<Diplomatic statement in Russian>"}}
      ]
    }}
    """
    res, tokens = call_json(client, model, prompt, temperature=0.6)
    clean = []
    silent = res.get("switzerland_concerned") is not True      # тема её не касается — пасхалка
    for s in res.get("statements") or []:          # правила проверяем кодом, а не надеждой на модель
        if not isinstance(s, dict) or s.get("speaker") not in speakers or not s.get("text"):
            continue
        clean.append({"speaker": s["speaker"],
                      "text": SWISS_LINE if (s["speaker"] == SWISS and silent) else str(s["text"])})
    res["statements"] = clean
    return res, tokens


def agent_simulate_conference_voting(client, model, conference_data: dict, final_proposal: str,
                                     player_country: str, player_vote: str, difficulty: str, solar_activity: int):
    participants = conference_data.get("participants", [])
    prompt = f"""
    You are the SUMMIT VOTING ARBITER.
    {_header(difficulty, solar_activity)}
    Summit: "{conference_data.get('title')}". Agenda: "{conference_data.get('topic')}".
    Debate so far: {_transcript(conference_data, 14)}.
    Final Resolution: "{final_proposal}".
    Participants: {dumps(participants)}.
    Player ({player_country}) Vote: {player_vote}.

    Every participant except the player votes according to its interests and what it said in the debate.
    SWITZERLAND RULE (easter egg): if "{SWISS}" participates, decide whether the resolution or the debate directly concerns Switzerland and report it in "switzerland_concerned". If NOT concerned, "{SWISS}" votes "Воздержался". If concerned, it votes by its interests.

    Return STRICTLY valid JSON:
    {{
      "switzerland_concerned": bool,
      "votes": {{
         "<Country Name>": {{"vote": "За"|"Против"|"Воздержался", "reason": "<Reason in Russian>"}}
      }},
      "resolution_passed": bool,
      "outcome_summary": "<Summary in Russian>",
      "positions_summary": "<Positions summary in Russian>",
      "minister_debrief": "<Minister debrief in Russian>"
    }}
    """
    res, tokens = call_json(client, model, prompt, temperature=0.3)
    if res.get("_error"):
        return res, tokens
    votes = res.get("votes") if isinstance(res.get("votes"), dict) else {}
    fixed = {}
    for p in participants:
        if p == player_country:
            continue
        v = votes.get(p) if isinstance(votes.get(p), dict) else {}
        vote = v.get("vote") if v.get("vote") in ("За", "Против", "Воздержался") else "Воздержался"
        reason = str(v.get("reason") or "Позиция не озвучена.")
        if p == SWISS and res.get("switzerland_concerned") is not True:
            vote, reason = "Воздержался", "Нейтралитет: тема Швейцарии не касается."
        fixed[p] = {"vote": vote, "reason": reason}
    res["votes"] = fixed
    res["resolution_passed"] = bool(res.get("resolution_passed"))
    return res, tokens


def agent_simulate_conference_walkout(client, model, conference_data: dict, player_country: str,
                                      difficulty: str, solar_activity: int):
    remaining = [c for c in conference_data.get("participants", []) if c != player_country]
    prompt = f"""
    Summit Walkout Simulation. The head of delegation of {player_country} (the human player) demonstratively leaves the summit.
    {_header(difficulty, solar_activity)}
    Summit: "{conference_data.get('title')}". Agenda: "{conference_data.get('topic')}".
    Debate so far: {_transcript(conference_data)}.
    Remaining delegations: {dumps(remaining)}.
    SWITZERLAND RULE (easter egg): if "{SWISS}" is among them, decide whether the agenda directly concerns Switzerland and report it in "switzerland_concerned". If NOT concerned, its text MUST BE EXACTLY: "{SWISS_LINE}".

    Return STRICTLY valid JSON:
    {{
      "switzerland_concerned": bool,
      "closing_dialogue": [{{"speaker": "<Country>", "text": "<Reaction in Russian>"}}],
      "walkout_reaction_summary": "<Reaction in Russian>",
      "closed_door_resolution": "<Resolution in Russian>",
      "minister_debrief": "<Debrief in Russian>"
    }}
    """
    res, tokens = call_json(client, model, prompt, temperature=0.5)
    silent = res.get("switzerland_concerned") is not True
    res["closing_dialogue"] = [
        {"speaker": s["speaker"], "text": SWISS_LINE if (s["speaker"] == SWISS and silent) else str(s.get("text", ""))}
        for s in res.get("closing_dialogue") or []
        if isinstance(s, dict) and s.get("speaker") in remaining
    ]
    return res, tokens


def agent_conference_foreign_minister_advice(client, model, conference_data: dict, player_country: str,
                                             difficulty: str, solar_activity: int):
    prompt = f"""You are the Foreign Minister of {player_country}.
    {_header(difficulty, solar_activity)}
    Summit: "{conference_data.get('title')}". Agenda: "{conference_data.get('topic')}".
    Participants: {dumps(conference_data.get('participants', []))}.
    Transcript: {_transcript(conference_data)}.

    Provide an urgent confidential brief to the sovereign in Russian (1-2 paragraphs)."""
    text, tokens, err = chat_text(client, model, [{"role": "system", "content": prompt},
                                                  {"role": "user", "content": "Ваш доклад, господин министр."}],
                                  temperature=0.5)
    if text:
        return text, tokens
    return f"Господин, связь с дипмиссией временно затруднена ({err}). Рекомендую занять выжидательную позицию.", 0
