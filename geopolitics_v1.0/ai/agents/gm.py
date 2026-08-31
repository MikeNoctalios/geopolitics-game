from ai.client import clean_json_response, estimate_tokens
from ai.prompts import get_alt_history_directive
from core.state import get_scenario_world_context
from core.commands import COMMAND_CATALOG_DOCS

def agent_gm_orchestrator(client, model, user_command, current_world_state):
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(current_world_state.get("is_alt_history", False), world_ctx)

    prompt = f"""
    You are the SUPREME COMMAND DISPATCHER AND PARSER.
    {ctx_block}
    Player Directive: "{user_command}".
    Current Player Nation: "{current_world_state.get('player_country')}".
    Current Date: {current_world_state.get('current_date')}.
    
    {COMMAND_CATALOG_DOCS}
    
    YOUR EXACT ROLE:
    Analyze the user's plain text input, select the required commands from the catalog above, and fill their exact parameters.
    
    CRITICAL EXAMPLES:
    1. "Добавь в полигон испытания подлодки Т-15 на 2 дня":
       -> commands: [
          {{"command": "ADD_RD_TEST", "params": {{"country": "{current_world_state.get('player_country')}", "name": "Подводная лодка Т-15", "category": "navy", "duration": "2 Дня", "specs": "Вертикальный взлет, пятиплоскостной стабилизатор"}}}}
       ]
       
    2. "Дай Ватикану атомную бомбу и напиши об этом в новостях":
       -> commands: [
          {{"command": "GRANT_EQUIPMENT", "params": {{"country": "Ватикан", "name": "Атомная бомба", "count": 1, "category": "ground", "type": "Оружие массового поражения"}}}},
          {{"command": "PUBLISH_WORLD_NEWS", "params": {{"title": "Сенсация: Ватикан получил атомное оружие", "desc": "Понтифик объявил об успешном создании ядерного арсенала."}}}},
          {{"command": "SET_LORE_DIRECTIVE", "params": {{"directive": "Ватикан обладает ядерным оружием"}}}}
       ]
       
    3. "Удали Францию":
       -> commands: [
          {{"command": "DELETE_COUNTRY", "params": {{"country": "Франция"}}}},
          {{"command": "SET_LORE_DIRECTIVE", "params": {{"directive": "Франция никогда не существовала в мировой истории"}}}}
       ]

    Return STRICTLY valid JSON:
    {{
      "confirmation_message": "<Short, polite technical confirmation in Russian>",
      "commands": [
         {{"command": "<COMMAND_NAME>", "params": {{...}}}}
      ]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.1)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)