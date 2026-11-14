from ai.agents._common import dumps
from ai.client import call_json


def agent_supreme_inspector_auditor(client, model, state, orders, proposed_package):
    prompt = f"""
    You are AGENT 6: SUPREME AUDITOR & CANONICAL QUALITY INSPECTOR.
    Verify consistency of the turn output against player decrees: "{orders}".
    Difficulty Setting: {state['difficulty']}.
    Current stability: {state['my_country'].get('stats', {}).get('stability')}.
    Proposed Package: {dumps(proposed_package)}

    Approve unless the package clearly ignores or contradicts the decrees.

    Return STRICTLY valid JSON:
    {{
      "approved": bool,
      "audit_notes": "<Brief Russian note>",
      "correction_patches": {{
          "adjust_stability": null,
          "add_missing_event": null
      }}
    }}
    (adjust_stability: int 0-100 or null; add_missing_event: {{"title": str, "desc": str}} or null)
    """
    return call_json(client, model, prompt, temperature=0.2, max_attempts=2)
