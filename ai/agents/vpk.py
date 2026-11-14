from ai.agents._common import dumps, lore
from ai.client import call_json
from core.military import CATEGORIES
from core.time_system import extract_year


def agent_military_industrial_complex(client, model, state, orders):
    year = extract_year(state["current_date"])
    me = state["my_country"]
    mil = me.get("military") if isinstance(me.get("military"), dict) else {}

    # Раньше агент не видел реестр и выдумывал названия, из-за чего выпуск техники не засчитывался.
    producing = [
        {"category": cat, "name": it.get("name"), "count": it.get("count", 0)}
        for cat in CATEGORIES for it in mil.get(cat, [])
        if it.get("production") and it.get("in_service", True)
    ]

    prompt = f"""
    You are AGENT 5: SUPREME MINISTER OF DEFENSE INDUSTRY & TESTING POLYGON.
    {lore(state)}
    Player Nation: {state['player_country']}.
    Current Year: {year}.
    Current Military Resources: {me.get('resources', 'Стандарт')}.
    Manpower: {me.get('stats', {}).get('manpower_approx', '?')}.
    Equipment currently IN PRODUCTION (use these EXACT names): {dumps(producing)}.
    Active R&D Projects: {dumps(state.get('rd_projects', []))}.
    Player's Orders regarding military/industry: "{orders}".

    TASKS:
    1. Progress active R&D projects (use their exact "id"): progress may only increase; update "polygon_report". If progress >= 100, set ready_for_tender=True.
    2. Calculate this turn's production output ONLY for the equipment listed above; "added_count" must be realistic for the country's scale and the period.
    3. Strict era check: in {year}, forbid anachronistic futuristic tech.
    4. CRITICAL: All text in fluent Russian.

    Return STRICTLY valid JSON:
    {{
      "updated_rd_projects": [{{"id": str, "name": str, "target_date": str, "progress": int, "status": str, "specs": str, "polygon_report": str, "ready_for_tender": bool}}],
      "production_increments": [{{"category": "infantry"|"ground"|"air"|"navy", "name": str, "added_count": int}}],
      "vpk_summary": "<Summary in Russian>"
    }}
    """
    return call_json(client, model, prompt, temperature=0.3)
