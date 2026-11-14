from ai.agents._common import active_country_names, dumps, lore
from ai.client import call_json


def agent_world_simulator(client, model, state, player_orders, recent_news_titles, alarm_clock=False):
    great_powers_goals = {
        name: {"region": c.get("region", "Европа"),
               "ambitions": c.get("ambitions", "Экспансия и влияние"),
               "fears": c.get("fears", "Угроза безопасности")}
        for name, c in state["countries"].items()
        if c.get("is_great_power", False) and name != state["player_country"]
    }

    if alarm_clock:
        regional_rule = """
    ALARM CLOCK TOTAL SIMULATION ACTIVE:
    Generate 6-10 major global events across ALL 4 MACRO-REGIONS:
    1. [Европа]
    2. [Северная и Южная Америка]
    3. [Азия и Океания]
    4. [Ближний Восток и Африка]
    Tag each event title with its region (e.g. '[Европа] Подписание пакта...').
    """
    else:
        regional_rule = "Generate 2-4 fresh autonomous world news events driven by Great Powers' goals."

    prompt = f"""
    You are AGENT 2: WORLD SIMULATOR & GLOBAL JOURNALIST.
    {lore(state)}
    Current Date: {state['current_date']}.
    Chaos Scale: {state['solar_activity']}/10.
    Great Powers' Agendas: {dumps(great_powers_goals)}.
    Known states (use these exact names): {dumps(active_country_names(state))}.
    Active Arcs: {dumps(state.get('ongoing_arcs', []))}.
    Player Decrees: "{player_orders}".
    Recent News Headlines (do not repeat): {dumps(recent_news_titles)}.

    {regional_rule}

    TASKS:
    1. Progress date by 1-5 days (crisis) or 1-4 months (calm). "new_date" MUST use the same format as the current date and be strictly LATER than it.
    2. Simulate autonomous great power events.
    3. Return valid Russian text.

    Return STRICTLY valid JSON:
    {{
      "new_date": "<Updated Date>",
      "new_world_events": [{{"date": "<Date>", "title": str, "desc": str}}],
      "flavor_events": [{{"date": "<Date>", "title": str, "desc": str}}]
    }}
    """
    return call_json(client, model, prompt, temperature=0.7)
