from ai.agents._common import dumps
from ai.client import call_json
from ai.prompts import get_alt_history_directive
from core.commands import COMMAND_CATALOG_DOCS
from core.state import get_scenario_world_context


def agent_gm_orchestrator(client, model, user_command, current_world_state):
    me = current_world_state.get("player_country")
    countries = list((current_world_state.get("countries") or {}).keys())
    lore = get_alt_history_directive(current_world_state.get("is_alt_history", False), get_scenario_world_context())

    prompt = f"""
    You are the SUPREME COMMAND DISPATCHER AND PARSER.
    {lore}
    Player Directive: "{user_command}".
    Current Player Nation: "{me}".
    Current Date: {current_world_state.get('current_date')}.
    Existing countries (use these EXACT names): {dumps(countries)}.

    {COMMAND_CATALOG_DOCS}

    YOUR ROLE:
    Map the human directive to one or more explicit commands from the catalog.

    CRITICAL EXAMPLES:
    1. "Проведи аудит армии / пересмотри вооружение / почисти дубли":
       -> commands: [{{"command": "AUDIT_ARMY", "params": {{"country": "{me}"}}}}]

    2. "Добавь в повестку дня отслеживание планов перевооружения":
       -> commands: [{{"command": "ADD_ISSUE", "params": {{"country": "{me}", "name": "Отслеживание планов перевооружения", "target_date": "1 Год", "status": "Активно"}}}}]

    3. "Очисти повестку дня":
       -> commands: [{{"command": "CLEAR_ISSUES", "params": {{"country": "{me}"}}}}]

    4. "Исправь армию на 850 тыс. человек":
       -> commands: [{{"command": "SET_MANPOWER", "params": {{"country": "{me}", "manpower": "~850 тыс. чел."}}}}]

    If the directive cannot be expressed with the catalog, return an empty "commands" list and explain why in "confirmation_message".

    Return STRICTLY valid JSON:
    {{
      "confirmation_message": "<Short, polite technical confirmation in Russian>",
      "commands": [
         {{"command": "<COMMAND_NAME>", "params": {{...}}}}
      ]
    }}
    """
    return call_json(client, model, prompt, temperature=0.1)
