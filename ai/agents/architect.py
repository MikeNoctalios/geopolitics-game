from ai.agents._common import dumps, lore
from ai.client import call_json


def agent_geopolitical_architect(client, model, state):
    """Запускается ПОСЛЕ мирового симулятора и арбитра: раньше он ничего не знал о событиях хода
    и «обнаруживал» расколы наугад."""
    world = [{"title": e.get("title"), "desc": e.get("desc")} for e in state.get("turn_world_events", [])]
    internal = [{"title": e.get("title"), "desc": e.get("desc")} for e in state.get("turn_player_events", [])]
    index = {n: {"status": c.get("status"), "regime": c.get("regime"), "region": c.get("region")}
             for n, c in state["countries"].items()}

    prompt = f"""
    You are AGENT 4: GEOPOLITICAL ARCHITECT & BORDER ARBITER.
    {lore(state)}
    Player Nation: {state['player_country']}.
    Current Date: {state['current_date']}.
    Existing states: {dumps(index)}.
    Active Storylines: {dumps(state.get('ongoing_arcs', []))}.
    Player Decrees this turn: "{state.get('orders', '')}".
    World events this turn: {dumps(world)}.
    Events in the player's country this turn: {dumps(internal)}.

    Based ONLY on the events above, detect whether a civil war, secession, collapse, or annexation
    that creates NEW states actually happened this turn. If nothing like that happened, return an empty list
    (this is the normal case). Split the player's own country ONLY if the events above explicitly describe its collapse.

    Return STRICTLY valid JSON:
    {{
      "country_transformations": [{{"hide_country": str, "spawn_countries": [{{"name": str, "is_great_power": bool, "has_civil_war": bool, "regime": str, "region": str, "stats": {{"stability": int, "war_support": int, "military_readiness": int, "manpower_approx": str}}}}]}}]
    }}
    """
    return call_json(client, model, prompt, temperature=0.3)
