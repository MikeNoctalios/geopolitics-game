import json
from ai.client import clean_json_response, estimate_tokens
from ai.prompts import get_chaos_persona_instructions, get_alt_history_directive
from core.state import get_scenario_world_context

def agent_simulate_conference_round(client, model, conference_data: dict, player_country: str, player_speech: str, difficulty: str, solar_activity: int):
    """
    Симулирует раунд высказываний участников с учетом сложности и шкалы хаоса.
    """
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(False, world_ctx)
    chaos_tone = get_chaos_persona_instructions(solar_activity)
    
    diff_instructions = {
        "Шутка": "DIFFICULTY: JOKE. AI nations are easily swayed, enthusiastic, and accept absurd ideas playfully.",
        "Лёгкий": "DIFFICULTY: EASY. AI nations prioritize cooperation and seek compromises with the player.",
        "Нормальный": "DIFFICULTY: NORMAL. Pragmatic balance of national interests.",
        "Хардкор": "DIFFICULTY: HARDCORE. AI nations are uncompromising, highly skeptical, and vigorously defend their borders/economy."
    }
    
    participants = conference_data.get("participants", [])
    topic = conference_data.get("topic", "Международный кризис")
    history = conference_data.get("dialogue", [])
    
    prompt = f"""
    You are the MULTILATERAL SUMMIT DIPLOMATIC ENGINE.
    {ctx_block}
    {chaos_tone}
    {diff_instructions.get(difficulty, diff_instructions['Нормальный'])}
    
    Summit Title: "{conference_data.get('title')}".
    Agenda: "{topic}".
    Secrecy: {conference_data.get('secrecy')}.
    Participants: {json.dumps(participants, ensure_ascii=False)}.
    Previous Dialogue: {json.dumps(history[-8:], ensure_ascii=False)}.
    Player ({player_country}) Statement: "{player_speech if player_speech else '(Player remained silent)'}".
    
    RULES:
    1. For each AI participant (excluding {player_country}), formulate their realistic response, counter-offer, or objection.
    2. A country may abstain with: "(Страна) воздерживается от комментариев."
    3. SWITZERLAND EASTER EGG: If "Швейцария" participates and the topic does not directly threaten Swiss territory, Switzerland's statement MUST BE EXACTLY: "Я бот и мне нечего сказать!"
    4. Text strictly in Russian.
    
    Return STRICTLY valid JSON:
    {{
      "statements": [
         {{"speaker": "<Country Name>", "text": "<Diplomatic statement matching chaos tone>"}}
      ]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.6)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)

def agent_simulate_conference_voting(client, model, conference_data: dict, final_proposal: str, player_country: str, player_vote: str, difficulty: str, solar_activity: int):
    """
    Симулирует голосование с учетом сложности и хаоса.
    """
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(False, world_ctx)
    chaos_tone = get_chaos_persona_instructions(solar_activity)
    
    diff_instructions = {
        "Шутка": "Votes 'За' easily on wild proposals.",
        "Лёгкий": "Cooperative voting stance.",
        "Нормальный": "Pragmatic calculation.",
        "Хардкор": "Strict rejection of unfavorable clauses."
    }
    
    participants = conference_data.get("participants", [])
    
    prompt = f"""
    You are the SUMMIT VOTING & RESOLUTION ARBITER.
    {ctx_block}
    {chaos_tone}
    {diff_instructions.get(difficulty, diff_instructions['Нормальный'])}
    
    Summit: "{conference_data.get('title')}".
    Final Resolution: "{final_proposal}".
    Participants: {json.dumps(participants, ensure_ascii=False)}.
    Player ({player_country}) Vote: {player_vote}.
    
    SWITZERLAND RULE: "Швейцария" ALWAYS votes "Воздержался".
    
    Return STRICTLY valid JSON:
    {{
      "votes": {{
         "<Country Name>": {{"vote": "За"|"Против"|"Воздержался", "reason": "<1-sentence Russian justification>"}}
      }},
      "resolution_passed": bool,
      "outcome_summary": "<Summary in Russian>",
      "positions_summary": "<Summary of who supported what and key debates in Russian>",
      "minister_debrief": "<Analytical debrief by Foreign Minister in Russian>"
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.3)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)

def agent_simulate_conference_walkout(client, model, conference_data: dict, player_country: str, difficulty: str, solar_activity: int):
    """
    Симулирует продолжение и финализацию саммита после демарша игрока.
    """
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(False, world_ctx)
    chaos_tone = get_chaos_persona_instructions(solar_activity)
    
    remaining = [c for c in conference_data.get("participants", []) if c != player_country]
    
    prompt = f"""
    You are the SUMMIT CRISIS ARBITER.
    {ctx_block}
    {chaos_tone}
    
    The sovereign of {player_country} has ABRUPTLY WALKED OUT OF THE SUMMIT (Diplomatic Demarche)!
    Remaining Participants: {json.dumps(remaining, ensure_ascii=False)}.
    Summit Topic: "{conference_data.get('topic')}".
    Dialogue So Far: {json.dumps(conference_data.get('dialogue', [])[-6:], ensure_ascii=False)}.
    
    TASK:
    1. Simulate the immediate reaction of remaining leaders to the walkout (anger, relief, mockery, or signing a pact behind player's back).
    2. Conclude their closed-door resolution without {player_country}.
    3. Generate a Foreign Minister debrief on consequences for {player_country}.
    
    Return STRICTLY valid JSON:
    {{
      "closing_dialogue": [
         {{"speaker": "<Country Name>", "text": "<Reaction to walkout and concluding thought in Russian>"}}
      ],
      "walkout_reaction_summary": "<Summary of world reaction to player's demarche in Russian>",
      "closed_door_resolution": "<Final pact or outcome agreed without player in Russian>",
      "minister_debrief": "<Minister's assessment of risks and fallout in Russian>"
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.5)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)

def agent_conference_foreign_minister_advice(client, model, conference_data: dict, player_country: str, difficulty: str, solar_activity: int):
    """
    Генерирует оперативный совет Министра иностранных дел по текущей ситуации на круглом столе.
    """
    world_ctx = get_scenario_world_context()
    ctx_block = get_alt_history_directive(False, world_ctx)
    chaos_tone = get_chaos_persona_instructions(solar_activity)
    
    prompt = f"""
    You are the Foreign Minister of {player_country} attending the summit "{conference_data.get('title')}".
    {ctx_block}
    {chaos_tone}
    Current Agenda: "{conference_data.get('topic')}".
    Transcript: {json.dumps(conference_data.get('dialogue', [])[-8:], ensure_ascii=False)}.
    
    Provide an urgent, confidential diplomatic briefing to your sovereign (1-2 paragraphs in Russian):
    - Who is leaning towards us and who is hostile?
    - What tactical counter-offer or stance do you advise?
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.5)
    return resp.choices[0].message.content.strip(), estimate_tokens(prompt + resp.choices[0].message.content)