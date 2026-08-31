import json
from ai.client import clean_json_response, estimate_tokens
from ai.prompts import get_alt_history_directive
from core.time_system import extract_year
from core.state import get_scenario_world_context

def agent_military_industrial_complex(client, model, state, orders):
    year = extract_year(state['current_date'])
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(state.get("is_alt_history", False), world_ctx)

    prompt = f"""
    You are AGENT 5: SUPREME MINISTER OF DEFENSE INDUSTRY & TESTING POLYGON.
    {ctx_block}
    Player Nation: {state['player_country']}.
    Current Year: {year}.
    Current Military Resources: {state['my_country'].get('resources', 'Стандарт')}.
    Active R&D Projects: {json.dumps(state.get('rd_projects', []), ensure_ascii=False)}.
    Player's Orders regarding military/industry: "{orders}".
    
    TASKS:
    1. Progress active R&D projects: increment progress %, update trial test reports ("polygon_report"). If progress >= 100, set ready_for_tender=True.
    2. Calculate production output for active in-service equipment.
    3. Strict era check: in {year}, forbid anachronistic futuristic tech.
    4. CRITICAL: All text in fluent Russian.
    
    Return STRICTLY valid JSON:
    {{
      "updated_rd_projects": [{{"id": str, "name": str, "base_equipment": str, "category": "infantry"|"ground"|"air"|"navy", "type": str, "target_date": str, "progress": int, "status": str, "specs": str, "polygon_report": str, "ready_for_tender": bool}}],
      "production_increments": [{{"category": "infantry"|"ground"|"air"|"navy", "name": str, "added_count": int}}],
      "vpk_summary": "<Summary in Russian>"
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.3)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)