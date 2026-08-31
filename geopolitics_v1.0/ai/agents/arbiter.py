import json
from ai.client import clean_json_response, estimate_tokens
from ai.prompts import get_alt_history_directive
from core.state import get_scenario_world_context

def agent_internal_arbiter(client, model, state, player_orders):
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(state.get("is_alt_history", False), world_ctx)
    
    diff_instructions = {
        "Шутка": "DIFFICULTY: JOKE. Player decrees always succeed comedically.",
        "Лёгкий": "DIFFICULTY: EASY. Factions eagerly back the sovereign.",
        "Нормальный": "DIFFICULTY: NORMAL. Realistic political trade-offs.",
        "Хардкор": "DIFFICULTY: HARDCORE. Severe friction, strikes, and political crises."
    }
    
    prompt = f"""
    You are AGENT 1: INTERNAL ARBITER for {state['player_country']}.
    {ctx_block}
    {diff_instructions.get(state['difficulty'], diff_instructions['Нормальный'])}
    
    Current Date: {state['current_date']}.
    Player Sovereign's Decrees: "{player_orders}".
    Current Issues: {json.dumps(state['my_country'].get('current_issues', []), ensure_ascii=False)}.
    Active Storylines (ongoing_arcs): {json.dumps(state.get('ongoing_arcs', []), ensure_ascii=False)}.
    
    TASKS:
    1. Calculate updated stats (0-100) for stability, war support, military readiness.
    2. Progress agenda (current_issues).
    3. Generate 0-1 spontaneous domestic event ONLY if warranted.
    4. Generate state headlines ("new_player_events") and foreign press excerpts ("press_excerpt").
    5. Register major narrative threads in "updated_ongoing_arcs".
    6. CRITICAL: All user-facing text MUST be in Russian.
    
    Return STRICTLY valid JSON:
    {{
      "updated_stats": {{"stability": int, "war_support": int, "military_readiness": int}},
      "updated_issues": [{{"name": str, "start_date": str, "target_date": str, "status": str}}],
      "new_internal_events": [{{"title": str, "desc": str, "type": "positive"|"negative", "impact": str}}],
      "new_player_events": [{{"title": str, "desc": str}}],
      "press_excerpt": {{"source": "<Newspaper Name>", "quote": "<Press quote in Russian>"}},
      "updated_ongoing_arcs": ["<List of active narrative threads>"]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.5)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)