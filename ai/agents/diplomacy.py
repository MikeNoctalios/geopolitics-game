from ai.agents._common import dumps, lore
from ai.client import call_json
from ai.prompts import get_chaos_persona_instructions


def agent_diplomacy(client, model, state, diplo_messages):
    me = state["player_country"]
    countries = state["countries"]

    # Профили только тех, с кем переписка, + великие державы (раньше в промпт шли отношения всех стран)
    involved = {d.get("to") for d in diplo_messages if isinstance(d, dict)}
    profiles = {}
    for name, c in countries.items():
        if name == me or c.get("status") == "Спящая":
            continue
        if name in involved or c.get("is_great_power"):
            profiles[name] = {
                "regime": c.get("regime"), "ambitions": c.get("ambitions"), "fears": c.get("fears"),
                "stance_to_player": (c.get("relations") or {}).get(me, "Нейтральное"),
                "relations": c.get("relations") or {},
            }

    prompt = f"""
    You are AGENT 3: DIPLOMATIC CORPS.
    {lore(state)}
    Player Nation: {me}.
    {get_chaos_persona_instructions(state['solar_activity'])}
    Player Dispatches: {dumps(diplo_messages)}.
    Country Profiles: {dumps(profiles)}.

    TASKS:
    1. Answer EVERY player dispatch with a characterful reply from the addressed country ("from" = that country, "to" = {me}), matching the Chaos tone.
    2. If Chaos >= 5, add 1 proactive incoming proposal or ultimatum from a country of your choice to {me}.
    3. If a country's attitude to the player changed, report it in "relation_updates" (short Russian phrase, e.g. "Враждебное", "Союзное").
    4. Use only the exact country names given. Fluent Russian text.

    Return STRICTLY valid JSON:
    {{
      "diplo_responses": [{{"from": str, "to": str, "message": str}}],
      "relation_updates": [{{"country": str, "stance": str}}]
    }}
    """
    return call_json(client, model, prompt, temperature=0.7)
