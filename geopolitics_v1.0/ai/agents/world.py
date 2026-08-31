import json
from ai.client import clean_json_response, estimate_tokens
from ai.prompts import get_alt_history_directive
from core.state import get_scenario_world_context

def agent_world_simulator(client, model, state, player_orders, recent_news_titles, alarm_clock=False):
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(state.get("is_alt_history", False), world_ctx)
    solar = state['solar_activity']
    
    # Сбор приоритетов великих держав
    great_powers_goals = {}
    for c_name, c_data in state['countries'].items():
        if c_data.get("is_great_power", False) and c_name != state['player_country']:
            great_powers_goals[c_name] = {
                "region": c_data.get("region", "Европа"),
                "ambitions": c_data.get("ambitions", "Экспансия и влияние"),
                "fears": c_data.get("fears", "Угроза безопасности")
            }

    regional_rule = """
    ALARM CLOCK TOTAL SIMULATION ACTIVE:
    Generate 6-10 major global events across ALL 4 MACRO-REGIONS:
    1. [Европа]
    2. [Северная и Южная Америка]
    3. [Азия и Океания]
    4. [Ближний Восток и Африка]
    Tag each event title with its region (e.g. '[Европа] Подписание пакта...').
    """ if alarm_clock else "Generate 2-4 fresh autonomous world news events driven by Great Powers' goals."

    prompt = f"""
    You are AGENT 2: WORLD SIMULATOR & GLOBAL JOURNALIST.
    {ctx_block}
    Current Date: {state['current_date']}.
    Chaos Scale: {solar}/10.
    Great Powers' Agendas & Spheres: {json.dumps(great_powers_goals, ensure_ascii=False)}.
    Active Arcs: {json.dumps(state.get('ongoing_arcs', []), ensure_ascii=False)}.
    Player's Actions (Keep in mind, World News must focus on OTHER powers, while player actions go to player events): "{player_orders}".
    Recent News Headlines (DO NOT REPEAT): {json.dumps(recent_news_titles, ensure_ascii=False)}.
    
    {regional_rule}
    
    TASKS:
    1. Progress date by 1-5 days (crisis/war) or 1-4 months (calm). Return "new_date".
    2. Simulate autonomous great power clashes and treaties based on their regional interests.
    3. Generate 1-2 flavor curios in "flavor_events".
    4. CRITICAL: All news text in Russian.
    
    Return STRICTLY valid JSON:
    {{
      "new_date": "<Updated Date>",
      "new_world_events": [{{"date": "<Date>", "title": str, "desc": str}}],
      "flavor_events": [{{"date": "<Date>", "title": str, "desc": str}}]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.7)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)