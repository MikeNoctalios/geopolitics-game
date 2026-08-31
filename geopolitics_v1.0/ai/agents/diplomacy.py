import json
from ai.client import clean_json_response, estimate_tokens
from ai.prompts import get_chaos_persona_instructions, get_alt_history_directive
from core.state import get_scenario_world_context

def agent_diplomacy(client, model, state, diplo_messages):
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(state.get("is_alt_history", False), world_ctx)
    solar = state['solar_activity']
    chaos_tone = get_chaos_persona_instructions(solar)

    prompt = f"""
    You are AGENT 3: DIPLOMATIC CORPS.
    {ctx_block}
    Player Nation: {state['player_country']}.
    {chaos_tone}
    Player Dispatches: {json.dumps(diplo_messages, ensure_ascii=False)}.
    World Stances: {json.dumps({k: v.get('relations', {}) for k, v in state['countries'].items() if v.get('status') == 'Активная'}, ensure_ascii=False)}.
    
    TASKS:
    1. Formulate characterful diplomatic replies.
    2. If Chaos >= 5, generate 1 proactive incoming proposal, insult, or ultimatum.
    3. CRITICAL: All text in fluent Russian.
    
    Return STRICTLY valid JSON:
    {{
      "diplo_responses": [{{"from": str, "to": str, "message": str}}]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.7)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)