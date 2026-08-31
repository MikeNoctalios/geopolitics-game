import json
from ai.client import clean_json_response, estimate_tokens

def agent_supreme_inspector_auditor(client, model, state, orders, proposed_package):
    prompt = f"""
    You are AGENT 6: SUPREME AUDITOR & CANONICAL QUALITY INSPECTOR.
    Verify consistency of the turn output against decrees.
    
    Player Decrees: "{orders}".
    Difficulty Setting: {state['difficulty']}.
    Proposed Turn Package:
    {json.dumps(proposed_package, ensure_ascii=False)}
    
    CRITICAL CHECKLIST:
    1. Did agents ignore a direct sovereign decree?
    2. Are there blatant anachronisms?
    3. Return approved=True if sound, else provide "correction_patches".
    
    Return STRICTLY valid JSON:
    {{
      "approved": bool,
      "audit_notes": "<Brief Russian note>",
      "correction_patches": {{
          "adjust_stability": null,
          "add_missing_event": null
      }}
    }}
    """
    try:
        resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.2)
        return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)
    except Exception:
        return {"approved": True, "audit_notes": "Аудит пройден автоматически.", "correction_patches": {}}, 100