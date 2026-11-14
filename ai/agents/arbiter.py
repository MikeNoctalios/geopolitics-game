from ai.agents._common import dumps, lore
from ai.client import call_json
from ai.prompts import get_difficulty_directive


def agent_internal_arbiter(client, model, state, player_orders):
    me = state["my_country"]
    prompt = f"""
    You are AGENT 1: INTERNAL ARBITER for {state['player_country']}.
    {lore(state)}
    {get_difficulty_directive(state['difficulty'])}

    Current Date: {state['current_date']}.
    Player Sovereign's Decrees: "{player_orders}".
    Current Stats (0-100): {dumps(me.get('stats', {}))}.
    Regime: {me.get('regime')} | Faction: {me.get('faction')} | Resources: {me.get('resources')}.
    Current Issues: {dumps(me.get('current_issues', []))}.
    Open Internal Incidents: {dumps([e.get('title') for e in state.get('internal_events', [])])}.
    Active Storylines (ongoing_arcs): {dumps(state.get('ongoing_arcs', []))}.

    TASKS:
    1. Calculate updated stats (0-100) for stability, war support, military readiness. Change them gradually from the Current Stats.
    2. Progress agenda (current_issues): return the FULL updated list.
    3. Generate 0-1 spontaneous domestic event ONLY if warranted; list titles of Open Incidents that are now resolved.
    4. Generate state headlines ("new_player_events") and foreign press excerpts ("press_excerpt").
    5. Return the FULL list of active narrative threads in "updated_ongoing_arcs": keep still-relevant existing ones verbatim, drop resolved ones, max 15.
    6. CRITICAL: All user-facing text MUST be in Russian.

    Return STRICTLY valid JSON:
    {{
      "updated_stats": {{"stability": int, "war_support": int, "military_readiness": int}},
      "updated_issues": [{{"name": str, "start_date": str, "target_date": str, "status": str}}],
      "new_internal_events": [{{"title": str, "desc": str, "type": "positive"|"negative", "impact": str}}],
      "resolved_internal_events": ["<title>"],
      "new_player_events": [{{"title": str, "desc": str}}],
      "press_excerpt": {{"source": "<Newspaper Name>", "quote": "<Press quote in Russian>"}},
      "updated_ongoing_arcs": ["<List of active narrative threads>"]
    }}
    """
    return call_json(client, model, prompt, temperature=0.5)
