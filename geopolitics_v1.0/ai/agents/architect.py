import json
from ai.client import clean_json_response, estimate_tokens
from ai.prompts import get_alt_history_directive
from core.state import get_scenario_world_context

def agent_geopolitical_architect(client, model, state):
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(state.get("is_alt_history", False), world_ctx)

    prompt = f"""
    You are AGENT 4: GEOPOLITICAL ARCHITECT & BORDER ARBITER.
    {ctx_block}
    Player Nation: {state['player_country']}.
    Current Date: {state['current_date']}.
    Active Storylines: {json.dumps(state.get('ongoing_arcs', []), ensure_ascii=False)}.
    
    Detect if any civil wars, faction realignments, collapses, or territorial annexations occurred this turn.
    
    Return STRICTLY valid JSON:
    {{
      "country_transformations": [{{"hide_country": str, "spawn_countries": [{{"name": str, "is_great_power": bool, "regime": str, "region": str, "stats": {{"stability": int, "war_support": int, "military_readiness": int, "manpower_approx": str}}}}]}}]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.3)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)