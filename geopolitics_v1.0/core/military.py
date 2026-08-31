import json
import streamlit as st
from core.time_system import extract_year
from ai.client import get_ai_client, load_config, clean_json_response

LANDLOCKED_NATIONS = {
    "Люксембург", "Сан-Марино", "Ватикан", "Лихтенштейн", "Андорра", "Швейцария", 
    "Австрия", "Чехословакия", "Венгрия", "Боливия", "Парагвай", "Монголия", 
    "Монгольская Народная Республика", "Тува", "Тувинская Народная Республика", 
    "Тибет", "Афганистан", "Непал", "Бутан", "Синьцзян"
}

MICROSTATES = {"Сан-Марино", "Ватикан", "Монако", "Лихтенштейн", "Андорра", "Люксембург"}

def normalize_military_category(raw_cat: str) -> str:
    """Приводит любые произвольные категории техники к 4 системным: infantry, ground, air, navy."""
    c = str(raw_cat).lower().strip()
    if any(k in c for k in ["пехот", "винтов", "автомат", "стрелк", "снаряж", "infantry", "small_arms", "бомб"]):
        return "infantry"
    if any(k in c for k in ["авиа", "самолет", "истребител", "бомбардировщик", "вертолет", "air", "plane"]):
        return "air"
    if any(k in c for k in ["флот", "корабл", "эсминец", "линкор", "подлодк", "катер", "крейсер", "navy", "ship", "субмарин"]):
        return "navy"
    return "ground"

def get_smart_fallback_military(country_name, date_str):
    year = extract_year(date_str)
    is_landlocked = country_name in LANDLOCKED_NATIONS
    is_micro = country_name in MICROSTATES

    inf_count = 500 if is_micro else 150000
    infantry = [
        {"name": f"Штатные винтовки ({country_name})", "type": "Винтовки пехоты", "count": inf_count, "production": not is_micro, "in_service": True, "specs": "Калибр 6.5-7.92 мм, магазинное питание", "evaluation": "Штатное вооружение пехоты.", "is_known_globally": True}
    ]
    ground = []
    if not is_micro:
        if year >= 1916:
            ground.append({"name": f"Легкая бронетехника ({year} г.)", "type": "Бронеавтомобиль / Танк", "count": 45, "production": True, "in_service": True, "specs": "Пулеметное или 37-мм пушечное вооружение", "evaluation": "Охранение и разведка.", "is_known_globally": True})
        ground.append({"name": "Полевая дивизионная артиллерия", "type": "Полевая артиллерия", "count": 140, "production": True, "in_service": True, "specs": "Калибр 75-76 мм", "evaluation": "Основа дивизионного огня.", "is_known_globally": True})
    air = []
    if not is_micro and year >= 1911:
        air.append({"name": f"Авиаотряд ({country_name})", "type": "Авиация", "count": 30, "production": True, "in_service": True, "specs": "Скорость 180-340 км/ч", "evaluation": "Разведка и связь.", "is_known_globally": True})
    navy = []
    if not is_landlocked and not is_micro:
        navy.append({"name": f"Патрульные канонерки ({country_name})", "type": "Эсминец / Канонерка", "count": 4, "production": True, "in_service": True, "specs": "Орудия 75-102 мм", "evaluation": "Охрана территориальных вод.", "is_known_globally": True})
    return {"infantry": infantry, "ground": ground, "air": air, "navy": navy}

def audit_military_catalog_ai(client, model, country_name, current_military, date_str, manpower_str):
    year = extract_year(date_str)
    is_landlocked = country_name in LANDLOCKED_NATIONS
    is_micro = country_name in MICROSTATES
    
    prompt = f"""
    You are the SUPREME GENERAL INSPECTOR OF ARMAMENTS.
    Audit, clean, restructure, and balance the military catalog for {country_name} as of {date_str} (Year: {year}).
    Manpower scale: {manpower_str}.
    
    Raw Catalog:
    {json.dumps(current_military, ensure_ascii=False)}
    
    AUDIT MANDATES:
    1. ALL text MUST BE IN FLUENT RUSSIAN.
    2. RECLASSIFY: Heavy artillery, field guns, SPGs -> 'ground'. Air defense/planes -> 'air'. Ships -> 'navy'.
    3. GEOGRAPHY: Nation is {'LANDLOCKED (navy MUST BE EMPTY `[]`)' if is_landlocked else 'COASTAL'}.
    4. SCALE: If microstate ({is_micro}), rifles 50-800, ground/air/navy MUST be `[]`.
    5. ERA INTEGRITY: In {year}, forbid anachronisms (no tanks before 1916, no planes before 1911, no modern drones/NATO tech).
    6. Preserve 'in_service' and 'production' flags.
    
    Return STRICTLY valid JSON:
    {{
      "infantry": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "ground": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "air": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "navy": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}]
    }}
    """
    try:
        resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.2)
        res = clean_json_response(resp.choices[0].message.content)
        if isinstance(res, dict) and "infantry" in res:
            return res
        return current_military
    except Exception:
        return current_military

def generate_military_for_country(client, model, country_name, date_str, manpower_str):
    year = extract_year(date_str)
    is_landlocked = country_name in LANDLOCKED_NATIONS
    is_micro = country_name in MICROSTATES

    geo_rule = "NATION IS LANDLOCKED! 'navy' array MUST be strictly empty `[]`." if is_landlocked else "Include realistic coastal/naval craft if appropriate, or `[]` if none."
    era_rule = f"Current year is {year}! Before 1916, tanks did not exist ('ground' must have only artillery/cavalry). Before 1911, planes did not exist ('air' must be `[]`). NO futuristic tech!"
    micro_rule = f"This is a microstate/guard ({manpower_str})! 50-800 rifles total, 0 tanks, 0 planes, 0 warships!" if is_micro else f"Regular nation scale: {manpower_str}. Provide a rich, historically authentic, diverse arsenal of 4-8 distinct items across active categories."

    prompt = f"""
    You are an expert military historian. Generate an authentic, diverse, era-accurate military catalog for {country_name} as of {date_str}.
    
    STRICT RULES:
    1. {geo_rule}
    2. {era_rule}
    3. {micro_rule}
    4. ALL text values MUST be written in Russian!
    
    Return STRICTLY valid JSON:
    {{
      "infantry": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "ground": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "air": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "navy": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}]
    }}
    """
    try:
        resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.3)
        res = clean_json_response(resp.choices[0].message.content)
        if isinstance(res, dict) and "infantry" in res:
            return res
        return get_smart_fallback_military(country_name, date_str)
    except Exception:
        return get_smart_fallback_military(country_name, date_str)

def ensure_military_loaded(country_name):
    c_data = st.session_state.countries.get(country_name, {})
    mil = c_data.get("military")
    if mil == "genit" or not isinstance(mil, dict) or not any(mil.values()):
        cfg_l = load_config()
        if cfg_l.get("api_key"):
            try:
                cl = get_ai_client(cfg_l["api_key"], cfg_l["base_url"])
                c_data["military"] = generate_military_for_country(
                    cl, cfg_l["model_name"], country_name, 
                    st.session_state.current_date, 
                    c_data.get("stats", {}).get("manpower_approx", "~100 тыс. чел.")
                )
            except Exception:
                c_data["military"] = get_smart_fallback_military(country_name, st.session_state.current_date)
        else:
            c_data["military"] = get_smart_fallback_military(country_name, st.session_state.current_date)