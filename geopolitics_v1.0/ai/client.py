import os
import json
import re
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def estimate_tokens(text: str) -> int:
    return max(1, len(str(text)) // 3)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return {"api_key": "", "base_url": "", "model_name": "gpt-4o-mini", "theme": "Светлая"}

def save_config(api_key, base_url, model_name, theme):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key, "base_url": base_url, "model_name": model_name, "theme": theme}, f)

def get_ai_client(api_key, base_url):
    kwargs = {
        "api_key": api_key if api_key else "dummy-key",
        "timeout": 45.0
    }
    if base_url: kwargs["base_url"] = base_url
    return OpenAI(**kwargs)

def clean_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    text = text.strip()

    try: return json.loads(text)
    except Exception: pass

    try:
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match: return json.loads(match.group(1))
    except Exception: pass

    try:
        cleaned = re.sub(r',\s*([\]}])', r'\1', text)
        return json.loads(cleaned)
    except Exception:
        return {
            "confirmation_message": "Указание принято. База данных скорректирована.",
            "state_mutations": {}
        }