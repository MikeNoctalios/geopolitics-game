import streamlit as st
import json
import os
import copy
import re
from openai import OpenAI

# ==========================================
# 0. СИСТЕМНЫЕ ПАПКИ И НАСТРОЙКИ
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SAVES_DIR = os.path.join(BASE_DIR, "saves")
SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios")

for d in [SAVES_DIR, SCENARIOS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 3)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return {"api_key": "", "base_url": "", "model_name": "gpt-4o-mini", "theme": "Светлая (по умолчанию)"}

def save_config(api_key, base_url, model_name, theme):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key, "base_url": base_url, "model_name": model_name, "theme": theme}, f)

# ==========================================
# 1. СЛОТОВАЯ СИСТЕМА СОХРАНЕНИЙ
# ==========================================
UI_KEYS = ("orders_", "diplo_", "chat_", "scen_uploader", "slot_uploader_", "note_area_page_")

def get_slot_path(slot_id):
    return os.path.join(SAVES_DIR, f"slot_{slot_id}.json")

def get_slot_info(slot_id):
    path = get_slot_path(slot_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
                return {
                    "exists": True,
                    "country": d.get("player_country", "Неизвестно"),
                    "turn": d.get("turn", 1),
                    "date": d.get("current_date", "1935"),
                    "difficulty": d.get("difficulty", "Нормальный"),
                    "solar": d.get("solar_activity", 1)
                }
        except Exception:
            return {"exists": False, "corrupted": True}
    return {"exists": False}

def save_game_to_slot(slot_id):
    path = get_slot_path(slot_id)
    save_data = {}
    for k, v in st.session_state.items():
        if not k.startswith(UI_KEYS) and k not in ["history"]:
            if isinstance(v, set):
                save_data[k] = list(v)
            else:
                save_data[k] = v
    with open(path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

def load_game_from_slot(slot_id):
    path = get_slot_path(slot_id)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for k, v in data.items():
        st.session_state[k] = v
    if "unread_messages" in st.session_state and isinstance(st.session_state.unread_messages, list):
        st.session_state.unread_messages = set(st.session_state.unread_messages)
    if "history" not in st.session_state: st.session_state.history = []
    if "pending_diplo" not in st.session_state: st.session_state.pending_diplo = []
    if "military_tenders" not in st.session_state: st.session_state.military_tenders = []
    if "military_mod_requests" not in st.session_state: st.session_state.military_mod_requests = []
    if "internal_events" not in st.session_state: st.session_state.internal_events = []
    if "token_usage" not in st.session_state: st.session_state.token_usage = {"turn": 0, "total": 0}
    if "autosave_interval" not in st.session_state: st.session_state.autosave_interval = 3
    if "gm_chat" not in st.session_state: st.session_state.gm_chat = []
    if "notes_pages" not in st.session_state:
        st.session_state.notes_pages = {str(i): "" for i in range(1, 100)}
    if "note_page_num" not in st.session_state:
        st.session_state.note_page_num = 1
    st.session_state.current_slot = slot_id
    st.session_state.in_game = True

def delete_slot(slot_id):
    path = get_slot_path(slot_id)
    if os.path.exists(path):
        os.remove(path)

# ==========================================
# 2. ПАРСЕР И ГЕНЕРАТОР ВООРУЖЕНИЯ
# ==========================================
def clean_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except Exception:
        pass

    try:
        cleaned = re.sub(r',\s*([\]}])', r'\1', text)
        return json.loads(cleaned)
    except Exception:
        return {
            "confirmation_message": "Указание принято. Гейммастер скорректировал баланс мира.",
            "state_mutations": {}
        }

LANDLOCKED_NATIONS = {
    "Люксембург", "Сан-Марино", "Ватикан", "Лихтенштейн", "Андорра", "Швейцария", 
    "Австрия", "Чехословакия", "Венгрия", "Боливия", "Парагвай", "Монголия", 
    "Монгольская Народная Республика", "Тува", "Тувинская Народная Республика", 
    "Тибет", "Афганистан", "Непал", "Бутан", "Синьцзян"
}

MICROSTATES = {"Сан-Марино", "Ватикан", "Монако", "Лихтенштейн", "Андорра", "Люксембург"}

def extract_year(date_str: str) -> int:
    for y in range(1800, 2030):
        if str(y) in str(date_str):
            return y
    return 1935

def get_smart_fallback_military(country_name, date_str):
    year = extract_year(date_str)
    is_landlocked = country_name in LANDLOCKED_NATIONS
    is_micro = country_name in MICROSTATES

    inf_count = 500 if is_micro else 150000
    infantry = [
        {
            "name": f"Штатные винтовки ({country_name})",
            "type": "Винтовки пехоты",
            "count": inf_count,
            "production": not is_micro,
            "in_service": True,
            "specs": "Калибр 6.5-7.92 мм, магазинное питание",
            "evaluation": "Штатное вооружение армии/гвардии.",
            "is_known_globally": True
        }
    ]

    ground = []
    if not is_micro:
        if year >= 1916:
            ground.append({
                "name": f"Легкая бронетехника ({year} г.)",
                "type": "Легкий танк / Броневик",
                "count": 45,
                "production": True,
                "in_service": True,
                "specs": "Пулеметное или легкое 37-мм пушечное вооружение",
                "evaluation": "Машины разведки и боевого охранения.",
                "is_known_globally": True
            })
        ground.append({
            "name": "Полевая дивизионная артиллерия",
            "type": "Полевая артиллерия",
            "count": 140,
            "production": True,
            "in_service": True,
            "specs": "Калибр 75-76 мм, дальность до 9 км",
            "evaluation": "Основа дивизионного огня.",
            "is_known_globally": True
        })

    air = []
    if not is_micro and year >= 1911:
        air_type = "Разведывательные аэропланы" if year < 1925 else "Истребители-бипланы"
        air.append({
            "name": f"{air_type} ({country_name})",
            "type": "Авиация",
            "count": 25 if year < 1925 else 75,
            "production": True,
            "in_service": True,
            "specs": "Скорость 160-330 км/ч",
            "evaluation": "Авиаотряды наблюдения и связи.",
            "is_known_globally": True
        })

    navy = []
    if not is_landlocked and not is_micro:
        navy.append({
            "name": f"Патрульные корабли и эсминцы ({country_name})",
            "type": "Эсминец / Канонерка",
            "count": 4,
            "production": True,
            "in_service": True,
            "specs": "Орудия 75-102 мм",
            "evaluation": "Охрана территориальных вод и портов.",
            "is_known_globally": True
        })

    return {"infantry": infantry, "ground": ground, "air": air, "navy": navy}

def generate_military_for_country(client, model, country_name, date_str, manpower_str):
    year = extract_year(date_str)
    is_landlocked = country_name in LANDLOCKED_NATIONS
    is_micro = country_name in MICROSTATES

    geo_rule = "СТРАНА НЕ ИМЕЕТ ВЫХОДА К МОРЮ! Поле 'navy' должно быть строго пустым массивом: `[]`." if is_landlocked else "Если у страны есть выход к морю, укажи правдоподобный флот или оставь пустой массив `[]`."
    era_rule = f"Сейчас {year} год! До 1916 года танков НЕ СУЩЕСТВОВАЛО (в поле 'ground' танков быть не должно, только артиллерия). До 1911 года военной авиации не существовало (поле 'air' пустое `[]`). Запрещены любые термины из будущего (никаких НАТО, БМП, тепловизоров, дронов, ПНВ)!"
    micro_rule = f"Это микрогосударство с крошечным гарнизоном/полицией ({manpower_str})! Количество винтовок строго в пределах 50-800 шт. Тяжелой техники, танков, самолетов и кораблей НЕТ (поля ground, air, navy — строгие пустые массивы `[]`)!" if is_micro else f"Численность армии: {manpower_str}."

    prompt = f"""
    Ты историк-архивист. Сгенерируй исторически и географически достоверный военный парк для державы {country_name} на дату {date_str}.
    
    СТРОГИЕ ПРАВИЛА:
    1. Все названия, типы, ТТХ и оценки СТРОГО НА РУССКОМ ЯЗЫКЕ!
    2. {geo_rule}
    3. {era_rule}
    4. {micro_rule}
    5. Не выдумывай несуществующие войска. Если армии не было — укажи только штатное оружие гвардии/жандармерии.
    
    Верни ТОЛЬКО валидный JSON:
    {{
      "infantry": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "ground": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "air": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}],
      "navy": [{{"name": str, "type": str, "count": int, "production": bool, "in_service": bool, "specs": str, "evaluation": str, "is_known_globally": bool}}]
    }}
    Пустые рода войск возвращай как `[]`.
    """
    try:
        resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.2)
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

# ==========================================
# 3. МНОГОАГЕНТНЫЕ ФУНКЦИИ
# ==========================================
def get_ai_client(api_key, base_url):
    kwargs = {"api_key": api_key if api_key else "dummy-key"}
    if base_url: kwargs["base_url"] = base_url
    return OpenAI(**kwargs)

def agent_internal_arbiter(client, model, state, player_orders):
    prompt = f"""
    Ты АГЕНТ 1: ВНУТРЕННИЙ АРБИТР державы {state['player_country']}.
    Сложность: {state['difficulty']}.
    Текущая дата: {state['current_date']}.
    Указы игрока: "{player_orders}".
    Текущие проблемы/повестка: {json.dumps(state['my_country'].get('current_issues', []), ensure_ascii=False)}.
    
    Верни ТОЛЬКО JSON на русском языке:
    {{
      "updated_stats": {{"stability": int, "war_support": int, "military_readiness": int}},
      "updated_issues": [{{"name": str, "start_date": str, "target_date": str, "status": str}}],
      "new_internal_events": [{{"title": str, "desc": str, "type": "positive"|"negative", "impact": str}}],
      "new_player_events": [{{"title": str, "desc": str}}],
      "press_excerpt": {{"source": "<Название издания>", "quote": "<Цитата зарубежной прессы об игроке>"}}
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.5)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)

def agent_world_simulator(client, model, state, player_orders):
    prompt = f"""
    Ты АГЕНТ 2: МИРОВОЙ СИМУЛЯТОР.
    Текущая дата: {state['current_date']}.
    Хаос (солнечная активность): {state['solar_activity']}/10.
    
    Верни ТОЛЬКО JSON на русском языке:
    {{
      "new_date": "<Новая дата, например '15 Марта 1935'>",
      "new_world_events": [{{"date": "<Промежуточная дата>", "title": str, "desc": str}}],
      "flavor_events": [{{"date": "<Промежуточная дата>", "title": str, "desc": str}}]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.7)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)

def agent_diplomacy(client, model, state, diplo_messages):
    prompt = f"""
    Ты АГЕНТ 3: ДИПЛОМАТИЯ.
    Страна игрока: {state['player_country']}.
    Входящие депеши игрока: {json.dumps(diplo_messages, ensure_ascii=False)}.
    
    Верни ТОЛЬКО JSON на русском языке:
    {{
      "diplo_responses": [{{"from": str, "to": str, "message": str}}]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.6)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)

def agent_world_architect(client, model, state):
    year = extract_year(state['current_date'])
    prompt = f"""
    Ты АГЕНТ 4: ГЛАВНЫЙ АРХИТЕКТОР МИРА И ВПК.
    Страна игрока: {state['player_country']}.
    Текущий исторический год: {year}.
    Запросы на модернизацию от игрока: {json.dumps(state.get('military_mod_requests', []), ensure_ascii=False)}.
    
    СТРОЖАЙШИЕ ПРАВИЛА:
    1. Все названия и ТТХ СТРОГО НА РУССКОМ ЯЗЫКЕ!
    2. Генерируй новые конкурсные прототипы (new_tenders) ТОЛЬКО если в military_mod_requests есть реальные заявки на модернизацию. Если заявок нет — массив new_tenders должен быть пустым `[]`!
    3. Техника должна СТРОГО соответствовать {year} году! Запрещены любые анахронизмы (никаких БМП, тепловизоров, дронов или стандартов НАТО в начале XX века).
    
    Верни ТОЛЬКО JSON:
    {{
      "new_tenders": [{{"name": str, "category": "infantry"|"ground"|"air"|"navy", "type": str, "specs": str, "evaluation": str, "cost_info": str}}],
      "country_transformations": [{{"hide_country": str, "spawn_countries": [{{"name": str, "is_great_power": bool, "regime": str, "stats": {{"stability": int, "war_support": int, "military_readiness": int, "manpower_approx": str}}}}]}}]
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.4)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)

def agent_gm_debug(client, model, user_command, current_world_state):
    prompt = f"""
    Ты ГЛАВНЫЙ ГЕЙММАСТЕР И АДМИНИСТРАТОР ИГРЫ.
    Команда админа: "{user_command}".
    Текущее состояние: Держава - {current_world_state.get('player_country')}, Дата - {current_world_state.get('current_date')}, Ход - {current_world_state.get('turn')}.
    
    Верни СТРОГО валидный JSON на русском языке:
    {{
      "confirmation_message": "Понял вас. Исправления внесены...",
      "state_mutations": {{
          "set_date": null,
          "add_world_event": null,
          "update_countries": {{}}
      }}
    }}
    """
    resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": prompt}], temperature=0.2)
    return clean_json_response(resp.choices[0].message.content), estimate_tokens(prompt + resp.choices[0].message.content)

# ==========================================
# 4. ФУНКЦИИ ЭКСПОРТА (ЛОГИ И ГАЗЕТА)
# ==========================================
def generate_raw_game_log_txt() -> str:
    lines = [f"=== ХРОНИКА ПАРТИИ: {st.session_state.player_country} ===", f"Сложность: {st.session_state.difficulty} | Хаос: {st.session_state.solar_activity}/10\n"]
    for arch in st.session_state.turn_archives:
        lines.append(f"--- ХОД {arch['turn']} ({arch['date']}) ---")
        if arch.get("player_events"):
            lines.append("ДЕЙСТВИЯ И СОБЫТИЯ СТРАНЫ:")
            for pe in arch["player_events"]:
                lines.append(f"  • {pe['title']}: {pe['desc']}")
        if arch.get("world_events"):
            lines.append("МИРОВЫЕ СОБЫТИЯ:")
            for we in arch["world_events"]:
                lines.append(f"  • [{we.get('date', arch['date'])}] {we['title']}: {we['desc']}")
        lines.append("")
    return "\n".join(lines)

def generate_newspaper_html() -> str:
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Хроника эпохи: {st.session_state.player_country}</title>
<style>
body {{ font-family: 'Georgia', serif; background-color: #f4f1ea; color: #1a1a1a; padding: 30px; line-height: 1.6; max-width: 900px; margin: auto; }}
h1 {{ text-align: center; border-bottom: 3px double #333; padding-bottom: 10px; text-transform: uppercase; letter-spacing: 2px; }}
.meta {{ text-align: center; font-style: italic; color: #555; margin-bottom: 30px; }}
.turn-block {{ background: #fff; padding: 20px; margin-bottom: 25px; border: 1px solid #dcd7cb; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }}
.turn-header {{ font-size: 1.3em; font-weight: bold; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-bottom: 15px; color: #8b0000; }}
.section-title {{ font-size: 1.1em; font-weight: bold; margin-top: 10px; color: #333; text-transform: uppercase; }}
.event {{ margin-bottom: 10px; padding-left: 10px; border-left: 3px solid #666; }}
.press-quote {{ background: #fdfbf7; border-left: 3px solid #b8860b; padding: 10px; font-style: italic; margin-top: 15px; }}
</style>
</head>
<body>
<h1>Вестник Мировой Истории</h1>
<div class="meta">Летопись правления державы: {st.session_state.player_country} | Эпоха: {st.session_state.current_date}</div>
"""
    for arch in st.session_state.turn_archives:
        html += f"""<div class="turn-block">
<div class="turn-header">Ход {arch['turn']} — {arch['date']}</div>"""
        
        if arch.get("player_events"):
            html += '<div class="section-title">🏛 Государственные дела и указы:</div>'
            for pe in arch["player_events"]:
                html += f'<div class="event"><b>{pe["title"]}</b><br>{pe["desc"]}</div>'
                
        if arch.get("world_events"):
            html += '<div class="section-title">🌍 Международные депеши:</div>'
            for we in arch["world_events"]:
                html += f'<div class="event"><b>[{we.get("date", arch["date"])}] {we["title"]}</b><br>{we["desc"]}</div>'
                
        if arch.get("press_excerpt"):
            p = arch["press_excerpt"]
            src = p.get("source", "Пресса") if isinstance(p, dict) else "Мировая пресса"
            quote = p.get("quote", "") if isinstance(p, dict) else str(p)
            if quote:
                html += f'<div class="press-quote">🗞 <b>{src}:</b> «{quote}»</div>'
                
        html += '</div>'
        
    html += "</body></html>"
    return html

# ==========================================
# 5. СТАРТ НОВОЙ СЕССИИ
# ==========================================
def start_new_game_session(slot_id, scenario_file, country, difficulty, solar_activity):
    with open(os.path.join(SCENARIOS_DIR, scenario_file), "r", encoding="utf-8") as f:
        scen = json.load(f)
        
    st.session_state.clear()
    st.session_state.in_game = True
    st.session_state.current_slot = slot_id
    st.session_state.scenario_name = scen.get("name", scenario_file)
    st.session_state.turn = 1
    st.session_state.current_date = scen.get("start_date", "1 Января 1935")
    st.session_state.player_country = country
    st.session_state.difficulty = difficulty
    st.session_state.solar_activity = solar_activity
    
    st.session_state.turn_archives = [{
        "turn": 1,
        "date": st.session_state.current_date,
        "world_events": scen.get("world_events", []),
        "flavor_events": [],
        "player_events": [],
        "press_excerpt": None
    }]
    
    st.session_state.countries = scen["countries"]
    st.session_state.countries[country]["status"] = "Активная"
    
    st.session_state.chats = {}
    st.session_state.unread_messages = set()
    st.session_state.internal_events = []
    st.session_state.military_tenders = []
    st.session_state.military_mod_requests = []
    
    st.session_state.advisor_chats = {
        "internal": [{"role": "assistant", "content": "Господин, внутренний порядок, законы и стабильность на моем контроле."}],
        "foreign": [{"role": "assistant", "content": "Внешнеполитическое ведомство готово к защите интересов державы."}],
        "defense": [{"role": "assistant", "content": "Генеральный штаб на связи. Докладываю о готовности армии и флота."}]
    }
    st.session_state.notes_pages = {str(i): "" for i in range(1, 100)}
    st.session_state.note_page_num = 1
    st.session_state.pending_diplo = []
    st.session_state.gm_chat = []
    st.session_state.token_usage = {"turn": 0, "total": 0}
    st.session_state.autosave_interval = 3
    st.session_state.history = []
    
    ensure_military_loaded(country)
    save_game_to_slot(slot_id)

# ==========================================
# 6. ГЛАВНЫЙ ИНТЕРФЕЙС
# ==========================================
st.set_page_config(page_title="Geopolitics AI Engine", layout="wide")
cfg = load_config()

# ==============================================================================
# ВЕТКА А: ГЛАВНОЕ МЕНЮ
# ==============================================================================
if not st.session_state.get("in_game", False):
    st.title("🌍 Geopolitics AI Engine")
    st.caption("Пошаговая геополитическая стратегия с многоагентным ИИ-гейммастером")
    
    if "menu_stage" not in st.session_state:
        st.session_state.menu_stage = 1
        
    if st.session_state.menu_stage == 1:
        with st.expander("⚙️ Настройки API и Провайдера", expanded=False):
            c_api = st.text_input("API Key", value=cfg.get("api_key", ""), type="password")
            c_url = st.text_input("Base URL", value=cfg.get("base_url", ""), help="Оставьте пустым для OpenAI или укажите URL провайдера (OpenRouter и др.)")
            c_mod = st.text_input("Model Name", value=cfg.get("model_name", "gpt-4o-mini"))
            if st.button("Сохранить настройки API"):
                save_config(c_api, c_url, c_mod, cfg.get("theme", ""))
                st.success("Настройки сохранены!")
                st.rerun()

        st.subheader("Ячейки сохранения")
        col1, col2, col3 = st.columns(3)
        cols = [col1, col2, col3]
        
        for i in range(1, 4):
            with cols[i-1]:
                info = get_slot_info(i)
                st.markdown(f"### Ячейка {i}")
                if info.get("exists"):
                    st.info(f"**{info['country']}**\n\nХод: {info['turn']} | {info['date']}\n\nСложность: {info['difficulty']} | Хаос: {info['solar']}/10")
                    if st.button(f"▶️ Продолжить", key=f"btn_load_{i}", type="primary", use_container_width=True):
                        load_game_from_slot(i)
                        st.rerun()
                    
                    with open(get_slot_path(i), "r", encoding="utf-8") as f:
                        save_json = f.read()
                    st.download_button(f"📥 Скачать файл", data=save_json, file_name=f"slot_{i}_{info['country']}.json", mime="application/json", use_container_width=True, key=f"dl_slot_{i}")
                    
                    with st.popover(f"🗑️ Удалить ячейку", use_container_width=True):
                        st.warning("Точно удалить сохранение?")
                        if st.button("Да, удалить навсегда", key=f"confirm_del_{i}", type="primary"):
                            delete_slot(i)
                            st.rerun()
                else:
                    st.markdown("*Пустая ячейка*")
                    if st.button(f"🚀 Новая игра", key=f"btn_new_{i}", type="primary", use_container_width=True):
                        st.session_state.target_slot = i
                        st.session_state.menu_stage = 2
                        st.rerun()
                    
                    up_file = st.file_uploader("Загрузить JSON", type=["json"], key=f"slot_uploader_{i}")
                    if up_file is not None:
                        try:
                            data = json.load(up_file)
                            with open(get_slot_path(i), "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            st.success("Сохранение загружено!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка: {e}")

    elif st.session_state.menu_stage == 2:
        st.subheader("Шаг 1: Выбор сценария, сложности и хаоса")
        if st.button("⬅️ Назад к ячейкам"):
            st.session_state.menu_stage = 1
            st.rerun()
            
        scenarios = [f for f in os.listdir(SCENARIOS_DIR) if f.endswith('.json')]
        sel_scen = st.selectbox("Доступные сценарии", scenarios)
        
        with open(os.path.join(SCENARIOS_DIR, sel_scen), "r", encoding="utf-8") as f:
            scen_d = json.load(f)
            
        st.write(f"**Описание:** {scen_d.get('description', '')}")
        st.write(f"**Дата старта:** {scen_d.get('start_date', '')}")
        
        st.divider()
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.markdown("#### Уровень сложности")
            diff = st.radio("Сложность", ["Шутка", "Лёгкий", "Нормальный", "Хардкор"], index=2)
        with col_s2:
            st.markdown("#### Шкала солнечной активности (Хаос)")
            solar = st.slider("Уровень хаоса поведения ботов", 0, 10, 2)
            
        if st.button("Далее: Выбор державы ➡️", type="primary"):
            st.session_state.selected_scenario = sel_scen
            st.session_state.selected_diff = diff
            st.session_state.selected_solar = solar
            st.session_state.menu_stage = 3
            st.rerun()

    elif st.session_state.menu_stage == 3:
        st.subheader("Шаг 2: Выбор державы")
        if st.button("⬅️ Назад"):
            st.session_state.menu_stage = 2
            st.rerun()
            
        with open(os.path.join(SCENARIOS_DIR, st.session_state.selected_scenario), "r", encoding="utf-8") as f:
            scen_d = json.load(f)
            
        countries = scen_d.get("countries", {})
        great = sorted([c for c, d in countries.items() if d.get("is_great_power")])
        minors = sorted([c for c, d in countries.items() if not d.get("is_great_power")])
        
        sel_country = st.selectbox("Выберите страну", great + ["---"] + minors)
        if sel_country and sel_country != "---":
            c_data = countries[sel_country]
            st.markdown(f"### {sel_country}")
            st.write(f"**Профиль:** {c_data.get('profile', '')}")
            st.write(f"**Режим:** {c_data.get('regime', '')} | **Фракция:** {c_data.get('faction', 'Нет')}")
            st.write(f"**Ресурсы:** {c_data.get('resources', 'Информация отсутствует')}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Стабильность", f"{c_data.get('stats', {}).get('stability', 0)}/100")
            c2.metric("Поддержка войны", f"{c_data.get('stats', {}).get('war_support', 0)}/100")
            c3.metric("Боеготовность", f"{c_data.get('stats', {}).get('military_readiness', 0)}/100")
            c4.metric("Оценка армии", c_data.get('stats', {}).get('manpower_approx', 'Неизвестно'))
            
            if st.button("🚀 Начать кампанию", type="primary", use_container_width=True):
                start_new_game_session(st.session_state.target_slot, st.session_state.selected_scenario, sel_country, st.session_state.selected_diff, st.session_state.selected_solar)
                st.rerun()

# ==============================================================================
# ВЕТКА Б: ИГРОВОЙ ЭКРАН
# ==============================================================================
else:
    if "unread_messages" not in st.session_state: st.session_state.unread_messages = set()
    if "history" not in st.session_state: st.session_state.history = []
    if "pending_diplo" not in st.session_state: st.session_state.pending_diplo = []
    if "internal_events" not in st.session_state: st.session_state.internal_events = []
    if "military_tenders" not in st.session_state: st.session_state.military_tenders = []
    if "military_mod_requests" not in st.session_state: st.session_state.military_mod_requests = []
    if "token_usage" not in st.session_state: st.session_state.token_usage = {"turn": 0, "total": 0}
    if "autosave_interval" not in st.session_state: st.session_state.autosave_interval = 3
    if "gm_chat" not in st.session_state: st.session_state.gm_chat = []
    if "notes_pages" not in st.session_state: st.session_state.notes_pages = {str(i): "" for i in range(1, 100)}
    if "note_page_num" not in st.session_state: st.session_state.note_page_num = 1

    # --- НАВИГАЦИЯ БЛОКНОТА (CALLBACKS) ---
    def prev_note_page():
        if st.session_state.note_page_num > 1:
            st.session_state.note_page_num -= 1

    def next_note_page():
        if st.session_state.note_page_num < 99:
            st.session_state.note_page_num += 1

    # --- САЙДБАР ---
    with st.sidebar:
        st.markdown(f"### 🏛 {st.session_state.player_country}")
        st.caption(f"Сложность: {st.session_state.difficulty} | Хаос: {st.session_state.solar_activity}/10")
        
        if st.button("💾 Сохранить и выйти в меню", use_container_width=True):
            save_game_to_slot(st.session_state.current_slot)
            st.session_state.in_game = False
            st.rerun()
            
        st.divider()
        
        # ВСПЛЫВАЮЩИЙ БЛОКНОТ
        with st.popover("📝 Блокнот", use_container_width=True):
            st.markdown("#### Личные заметки")
            col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
            with col_p1:
                st.button("⬅️", on_click=prev_note_page, key="btn_prev_note_cb")
            with col_p2:
                st.number_input("Стр.", min_value=1, max_value=99, key="note_page_num", label_visibility="collapsed")
            with col_p3:
                st.button("➡️", on_click=next_note_page, key="btn_next_note_cb")
                        
            cur_p_key = str(st.session_state.note_page_num)
            if cur_p_key not in st.session_state.notes_pages:
                st.session_state.notes_pages[cur_p_key] = ""
                
            note_val = st.text_area(f"Страница {cur_p_key}:", value=st.session_state.notes_pages[cur_p_key], height=240, key=f"note_area_page_{cur_p_key}")
            st.session_state.notes_pages[cur_p_key] = note_val
            
        # ДЕБАГ МЕНЮ И ЭКСПОРТ
        with st.expander("🛠 Debug, Гейммастер и Экспорт", expanded=False):
            st.markdown(f"**Расход токенов:** За ход: ~{st.session_state.token_usage['turn']} | Всего: ~{st.session_state.token_usage['total']}")
            st.session_state.autosave_interval = st.number_input("Автосохранение каждые (ходов):", min_value=1, max_value=10, value=st.session_state.autosave_interval)
            
            if st.button("↩️ Откатить ход"):
                if st.session_state.history:
                    last_s = st.session_state.history.pop()
                    for k, v in last_s.items():
                        st.session_state[k] = v
                    save_game_to_slot(st.session_state.current_slot)
                    st.success("Ход откачен!")
                    st.rerun()
                else:
                    st.error("История пуста.")
                    
            st.divider()
            st.markdown("#### 📤 Экспорт материалов партии")
            raw_log_txt = generate_raw_game_log_txt()
            st.download_button("📥 Скачать лог партии (.txt)", data=raw_log_txt, file_name=f"log_{st.session_state.player_country}_turn{st.session_state.turn}.txt", mime="text/plain", use_container_width=True)
            
            newspaper_html = generate_newspaper_html()
            st.download_button("🗞️ Скачать газетную хронику (.html)", data=newspaper_html, file_name=f"gazette_{st.session_state.player_country}_turn{st.session_state.turn}.html", mime="text/html", use_container_width=True)

            st.divider()
            st.markdown("#### Чат с Гейммастером")
            for g_msg in st.session_state.gm_chat[-4:]:
                with st.chat_message(g_msg["role"]):
                    st.write(g_msg["content"])
                    
            gm_input = st.text_input("Мета-указание Гейммастеру:", key="gm_command_input")
            if st.button("Отправить Гейммастеру"):
                if gm_input and cfg.get("api_key"):
                    cl = get_ai_client(cfg["api_key"], cfg["base_url"])
                    with st.spinner("Гейммастер перестраивает мир..."):
                        try:
                            gm_res, t_count = agent_gm_debug(cl, cfg["model_name"], gm_input, {
                                "player_country": st.session_state.player_country,
                                "countries": st.session_state.countries,
                                "current_date": st.session_state.current_date,
                                "turn": st.session_state.turn
                            })
                            st.session_state.token_usage["total"] += t_count
                            st.session_state.gm_chat.append({"role": "user", "content": gm_input})
                            st.session_state.gm_chat.append({"role": "assistant", "content": gm_res.get("confirmation_message", "Принято к исполнению.")})
                            
                            mut = gm_res.get("state_mutations", {})
                            if mut.get("set_date"): st.session_state.current_date = mut["set_date"]
                            if mut.get("add_world_event"):
                                st.session_state.turn_archives[-1]["world_events"].append({"date": st.session_state.current_date, "title": mut["add_world_event"]["title"], "desc": mut["add_world_event"]["desc"]})
                            if mut.get("update_countries"):
                                for c_n, c_v in mut["update_countries"].items():
                                    if c_n in st.session_state.countries: st.session_state.countries[c_n].update(c_v)
                        except Exception:
                            st.session_state.gm_chat.append({"role": "assistant", "content": "Указание зафиксировано в мировом каноне."})
                        st.rerun()

    # --- ОСНОВНОЙ ЭКРАН ИГРЫ ---
    st.title(f"Ход {st.session_state.turn} | {st.session_state.current_date}")

    diplo_badge = f"🤝 Дипломатия ({len(st.session_state.unread_messages)} 📩)" if st.session_state.unread_messages else "🤝 Дипломатия"

    tab_news, tab_country, tab_diplo, tab_army, tab_advisor = st.tabs([
        "📰 Сводки и Новости", 
        "🏛 Управление", 
        diplo_badge,
        "🪖 Армия и ВПК",
        "🧠 Советники"
    ])

    # ==========================================
    # ВКЛАДКА 1: НОВОСТИ
    # ==========================================
    with tab_news:
        for arch in reversed(st.session_state.turn_archives):
            with st.expander(f"📌 Ход {arch['turn']} — {arch['date']}", expanded=(arch['turn'] == st.session_state.turn)):
                col_nw1, col_nw2 = st.columns(2)
                with col_nw1:
                    st.markdown("#### 🌍 Мировая арена")
                    world_evs = list(reversed(arch.get("world_events", [])))
                    for we in world_evs:
                        st.info(f"**[{we.get('date', arch['date'])}] {we['title']}**\n\n{we['desc']}")
                    
                    flavor_evs = list(reversed(arch.get("flavor_events", [])))
                    if flavor_evs:
                        with st.expander("🎭 Прочее (Слухи, культура, курьёзы)", expanded=False):
                            for fe in flavor_evs:
                                st.caption(f"**[{fe.get('date', arch['date'])}] {fe['title']}:** {fe['desc']}")
                
                with col_nw2:
                    st.markdown("#### 🏛 О нас")
                    player_evs = list(reversed(arch.get("player_events", [])))
                    if not player_evs:
                        st.write("Специфических событий не зафиксировано.")
                    for pe in player_evs:
                        st.success(f"**{pe['title']}**\n\n{pe['desc']}")
                        
                    if arch.get("press_excerpt"):
                        p_data = arch["press_excerpt"]
                        if isinstance(p_data, str):
                            try: p_data = json.loads(p_data)
                            except Exception: p_data = {"source": "Иностранная пресса", "quote": p_data}
                        if isinstance(p_data, dict):
                            src = p_data.get("source", "Мировая пресса")
                            quote_t = p_data.get("quote", "")
                            if quote_t:
                                with st.expander("🗞️ Мировая пресса о нашей державе", expanded=False):
                                    st.markdown(f"*{src}:* «{quote_t}»")

    # ==========================================
    # ВКЛАДКА 2: УПРАВЛЕНИЕ
    # ==========================================
    with tab_country:
        my_c = st.session_state.countries[st.session_state.player_country]
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Стабильность", f"{my_c['stats']['stability']}/100")
        col_m2.metric("Поддержка войны", f"{my_c['stats']['war_support']}/100")
        col_m3.metric("Боеготовность", f"{my_c['stats']['military_readiness']}/100")
        col_m4.metric("Оценка армии", my_c['stats'].get('manpower_approx', 'Неизвестно'))
        
        st.write(f"**Ресурсы:** {my_c.get('resources', 'Стандартное обеспечение')}")
        
        if st.session_state.internal_events:
            st.markdown("### ⚡ Внутренние происшествия")
            for ev in st.session_state.internal_events:
                if ev.get("type") == "positive":
                    st.success(f"🟢 **{ev['title']}**\n\n{ev['desc']}\n\n*Эффект:* {ev.get('impact', '')}")
                else:
                    st.error(f"🔴 **{ev['title']}**\n\n{ev['desc']}\n\n*Эффект:* {ev.get('impact', '')}")
                    
        st.divider()
        st.subheader("📌 Повестка дня и процессы")
        if not my_c.get('current_issues'):
            st.write("Нет активных процессов.")
        else:
            for issue in my_c['current_issues']:
                st.warning(f"**{issue['name']}** | Дедлайн: {issue.get('target_date', 'Бессрочно')} | Статус: *{issue['status']}*")
                
        st.subheader("Приказы на текущий ход")
        st.text_area("Опишите политические, экономические и мобилизационные решения:", key=f"orders_{st.session_state.turn}", height=140)

    # ==========================================
    # ВКЛАДКА 3: ДИПЛОМАТИЯ
    # ==========================================
    with tab_diplo:
        all_targets = [c for c in st.session_state.countries.keys() if c != st.session_state.player_country]
        
        def diplo_sort_key(c_name):
            is_unread = 0 if c_name in st.session_state.unread_messages else 1
            is_great = 0 if st.session_state.countries[c_name].get("is_great_power") else 1
            return (is_unread, is_great, c_name)
            
        sorted_targets = sorted(all_targets, key=diplo_sort_key)
        
        def format_diplo_label(c_name):
            c_info = st.session_state.countries[c_name]
            prefix = ""
            if c_name in st.session_state.unread_messages: prefix += "📩 "
            if c_info.get("is_great_power"): prefix += "⭐ "
            overlord = f" ({c_info['overlord']})" if c_info.get("overlord") else ""
            return f"{prefix}{c_name}{overlord}"

        if "active_diplo_country" not in st.session_state or st.session_state.active_diplo_country not in sorted_targets:
            st.session_state.active_diplo_country = sorted_targets[0] if sorted_targets else None

        target_c = st.selectbox("Выберите державу для связи:", sorted_targets, format_func=format_diplo_label, key="selectbox_diplo_target")
        st.session_state.active_diplo_country = target_c

        if target_c in st.session_state.unread_messages:
            st.session_state.unread_messages.remove(target_c)

        t_data = st.session_state.countries[target_c]
        
        with st.expander(f"Досье: {target_c}", expanded=True):
            cd1, cd2 = st.columns(2)
            with cd1:
                st.write(f"**Режим:** {t_data.get('regime', 'Неизвестно')}")
                st.write(f"**Фракция:** {t_data.get('faction', 'Нет')}")
                st.write(f"**Отношение к нам:** {t_data.get('relations', {}).get(st.session_state.player_country, 'Нейтральное')}")
            with cd2:
                st.write(f"**Ресурсы:** {t_data.get('resources', 'Данные разведки скудны')}")
                st.write(f"**Армия (оценка):** {t_data.get('stats', {}).get('manpower_approx', '~500 тыс. чел.')}")

        chat_k = f"{min(st.session_state.player_country, target_c)}-{max(st.session_state.player_country, target_c)}"
        if chat_k not in st.session_state.chats: st.session_state.chats[chat_k] = []
        
        st.subheader(f"Переписка: {target_c}")
        for msg in st.session_state.chats[chat_k][-10:]:
            if msg["from"] == st.session_state.player_country:
                st.markdown(f"<div style='text-align: right; color: #4CAF50; padding: 4px;'><b>Вы:</b> {msg['text']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: left; color: #2196F3; padding: 4px;'><b>{msg['from']}:</b> {msg['text']}</div>", unsafe_allow_html=True)
        st.divider()

        def send_diplo_action():
            msg_t = st.session_state.diplo_msg_input
            if msg_t and target_c:
                st.session_state.chats[chat_k].append({"from": st.session_state.player_country, "text": msg_t})
                st.session_state.pending_diplo.append({"from": st.session_state.player_country, "to": target_c, "text": msg_t})
                st.session_state.diplo_msg_input = ""

        st.text_area("Текст депеши:", key="diplo_msg_input", height=90)
        st.button("Отправить депешу", on_click=send_diplo_action, type="secondary")

    # ==========================================
    # ВКЛАДКА 4: АРМИЯ И ВПК
    # ==========================================
    with tab_army:
        ensure_military_loaded(st.session_state.player_country)
        my_c = st.session_state.countries[st.session_state.player_country]
        my_mil = my_c.get("military", {})
        if not isinstance(my_mil, dict):
            my_mil = {"infantry": [], "ground": [], "air": [], "navy": []}
            my_c["military"] = my_mil
        
        mil_category = st.radio(
            "Категория вооружения",
            ["🪖 Пехотное вооружение", "🚜 Бронетехника и Арт", "✈️ Авиация", "⚓ Флот", "🔍 Разведка армий"],
            horizontal=True,
            label_visibility="collapsed",
            key="mil_category_selector_fixed"
        )
        
        cat_map = {
            "🪖 Пехотное вооружение": "infantry",
            "🚜 Бронетехника и Арт": "ground",
            "✈️ Авиация": "air",
            "⚓ Флот": "navy"
        }
        
        # Конкурсы ВПК
        if st.session_state.military_tenders:
            st.markdown("### 🏆 Конкурсные предложения ВПК")
            for idx, tender in enumerate(st.session_state.military_tenders):
                with st.container(border=True):
                    st.markdown(f"**Прототип: {tender['name']}** ({tender.get('type', '')})")
                    st.write(f"**Характеристики:** {tender.get('specs', '')}")
                    st.write(f"**Оценка полигона:** *{tender.get('evaluation', '')}*")
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        if st.button(f"Принять на вооружение", key=f"acc_t_{idx}"):
                            cat = tender.get("category", "ground")
                            my_mil.setdefault(cat, []).append({
                                "name": tender["name"], "type": tender["type"], "count": 100,
                                "production": True, "in_service": True, "specs": tender["specs"],
                                "evaluation": tender["evaluation"], "is_known_globally": False
                            })
                            st.session_state.military_tenders.pop(idx)
                            st.rerun()
                    with col_t2:
                        if st.button(f"Отклонить образец", key=f"rej_t_{idx}"):
                            st.session_state.military_tenders.pop(idx)
                            st.rerun()

        if mil_category in cat_map:
            c_key = cat_map[mil_category]
            
            if c_key == "infantry":
                st.info(f"📊 Численность действующей пехоты и мобилизационного ресурса: **{my_c['stats'].get('manpower_approx', 'Неизвестно')}**")
                
            items = my_mil.get(c_key, [])
            
            if not items:
                if c_key == "navy":
                    st.warning("⚓ Военно-морской флот отсутствует (держава не имеет флота или выхода к морю).")
                elif c_key == "air":
                    st.info("✈️ Военная авиация отсутствует на вооружении данной державы.")
                elif c_key == "ground":
                    st.info("🚜 Тяжелая бронетехника отсутствует на вооружении.")
                else:
                    st.write("На вооружении нет единиц данной категории.")
            else:
                for j, eq in enumerate(items):
                    status_str = "На вооружении" if eq.get("in_service") else "Снято с вооружения"
                    prod_str = "В производстве" if eq.get("production") else "Производство остановлено"
                    
                    with st.expander(f"{eq['name']} — {eq.get('count', 0):,} ед. [{status_str} | {prod_str}]", expanded=True):
                        st.write(f"**Тип:** {eq.get('type', '')}")
                        st.write(f"**ТТХ:** {eq.get('specs', '')}")
                        st.write(f"**Оценка военных:** *{eq.get('evaluation', '')}*")
                        
                        c_b1, c_b2, c_b3 = st.columns(3)
                        with c_b1:
                            if eq.get("production"):
                                if st.button("Снять с производства", key=f"stop_prod_{c_key}_{j}"):
                                    eq["production"] = False
                                    st.rerun()
                            else:
                                if eq.get("in_service"):
                                    if st.button("Возобновить выпуск", key=f"start_prod_{c_key}_{j}"):
                                        eq["production"] = True
                                        st.rerun()
                        with c_b2:
                            if eq.get("in_service"):
                                with st.popover("Снять с вооружения"):
                                    st.warning("Списание с вооружения также остановит производство. Подтвердить?")
                                    if st.button("Да, списать с вооружения", key=f"retire_{c_key}_{j}"):
                                        eq["in_service"] = False
                                        eq["production"] = False
                                        st.rerun()
                            else:
                                st.caption("Единица списана")
                        with c_b3:
                            is_modded = any(req.get("name") == eq["name"] for req in st.session_state.military_mod_requests if isinstance(req, dict))
                            if is_modded:
                                st.info("⏳ Модернизация в разработке")
                            else:
                                if st.button("Запросить модернизацию", key=f"mod_{c_key}_{j}"):
                                    st.session_state.military_mod_requests.append({
                                        "name": eq["name"],
                                        "category": c_key,
                                        "specs": eq.get("specs", "")
                                    })
                                    st.rerun()

        elif mil_category == "🔍 Разведка армий":
            st.markdown("#### 🕵️ Разведданные Генерального штаба")
            other_c = st.selectbox("Выберите державу для изучения разведки:", [c for c in st.session_state.countries.keys() if c != st.session_state.player_country])
            ensure_military_loaded(other_c)
            other_c_data = st.session_state.countries[other_c]
            other_mil = other_c_data.get("military", {})
            
            st.metric(f"Оценочная численность армии ({other_c})", other_c_data.get("stats", {}).get("manpower_approx", "~500 тыс. чел."))
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                with st.expander("🪖 Стрелковое вооружение", expanded=True):
                    known_inf = [it for it in other_mil.get("infantry", []) if it.get("is_known_globally")]
                    if known_inf:
                        for kit in known_inf: st.write(f"• **{kit['name']}** (~{kit.get('count', '?')} ед.)")
                    else: st.caption("Конкретные образцы засекречены или отсутствуют.")
                    
                with st.expander("🚜 Бронетехника и артиллерия", expanded=True):
                    known_gr = [it for it in other_mil.get("ground", []) if it.get("is_known_globally")]
                    if known_gr:
                        for kit in known_gr: st.write(f"• **{kit['name']}** ({kit.get('type', '')}) — ~{kit.get('count', '?')} ед.")
                    else: st.caption("Тяжелая техника отсутствует или засекречена.")
                    
            with col_r2:
                with st.expander("✈️ Военная авиация", expanded=True):
                    known_air = [it for it in other_mil.get("air", []) if it.get("is_known_globally")]
                    if known_air:
                        for kit in known_air: st.write(f"• **{kit['name']}** ({kit.get('type', '')}) — ~{kit.get('count', '?')} ед.")
                    else: st.caption("Военная авиация отсутствует или засекречена.")
                    
                with st.expander("⚓ Военно-морской флот", expanded=True):
                    known_navy = [it for it in other_mil.get("navy", []) if it.get("is_known_globally")]
                    if known_navy:
                        for kit in known_navy: st.write(f"• **{kit['name']}** ({kit.get('type', '')}) — {kit.get('count', '?')} ед.")
                    else:
                        if other_c in LANDLOCKED_NATIONS:
                            st.caption("⚓ Держава не имеет выхода к морю.")
                        else:
                            st.caption("Флот отсутствует или скрыт туманом войны.")

    # ==========================================
    # ВКЛАДКА 5: СОВЕТНИКИ
    # ==========================================
    with tab_advisor:
        adv_sel = st.radio(
            "Министерство",
            ["Министр внутренних дел", "Министр иностранных дел", "Министр обороны"],
            horizontal=True,
            label_visibility="collapsed",
            key="advisor_selector_fixed"
        )
        
        role_map = {
            "Министр внутренних дел": "internal",
            "Министр иностранных дел": "foreign",
            "Министр обороны": "defense"
        }
        r_k = role_map[adv_sel]
        
        for a_msg in st.session_state.advisor_chats[r_k][-6:]:
            with st.chat_message(a_msg["role"]):
                st.write(a_msg["content"])
                
        if a_prompt := st.chat_input(f"Спросить ({adv_sel})...", key=f"chat_input_field_{r_k}"):
            st.session_state.advisor_chats[r_k].append({"role": "user", "content": a_prompt})
            st.rerun()

        if st.session_state.advisor_chats[r_k][-1]["role"] == "user":
            if cfg.get("api_key"):
                cl = get_ai_client(cfg["api_key"], cfg["base_url"])
                with st.spinner("Министр готовит ответ..."):
                    my_c = st.session_state.countries[st.session_state.player_country]
                    sys_p = f"Ты {adv_sel} державы {st.session_state.player_country}. Отвечай строго на русском языке, предельно кратко и тезисно (1-2 абзаца). Армия: {my_c['stats'].get('military_readiness')}, Стабильность: {my_c['stats'].get('stability')}."
                    r_res = cl.chat.completions.create(model=cfg["model_name"], messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": st.session_state.advisor_chats[r_k][-1]["content"]}], temperature=0.6)
                    st.session_state.advisor_chats[r_k].append({"role": "assistant", "content": r_res.choices[0].message.content})
                    st.rerun()

    # ==========================================
    # КНОПКА ЗАВЕРШЕНИЯ ХОДА
    # ==========================================
    st.divider()

    warnings = []
    if st.session_state.unread_messages:
        warnings.append(f"Непрочитанные депеши от: {', '.join(st.session_state.unread_messages)}")
    if st.session_state.military_tenders:
        warnings.append(f"Не рассмотрены конкурсные предложения ВПК ({len(st.session_state.military_tenders)} шт.)")
    orders_current = st.session_state.get(f"orders_{st.session_state.turn}", "").strip()
    if not orders_current:
        warnings.append("Вы не отдали никаких приказов на текущий ход")
    if any(ev.get("type") == "negative" for ev in st.session_state.internal_events):
        warnings.append("В стране действуют активные негативные происшествия!")

    col_nxt1, col_nxt2, col_nxt3 = st.columns([1, 2, 1])
    with col_nxt2:
        if warnings:
            with st.popover("⚠️ ЗАВЕРШИТЬ ХОД (Есть нерешённые вопросы)", use_container_width=True):
                st.error("Обратите внимание перед переходом хода:")
                for w in warnings: st.write(f"• {w}")
                st.divider()
                if st.button("Всё равно подтвердить и завершить ход", type="primary", use_container_width=True):
                    execute_turn = True
                else: execute_turn = False
        else:
            execute_turn = st.button("⏭ ЗАВЕРШИТЬ ХОД", type="primary", use_container_width=True)

    if execute_turn:
        if not cfg.get("api_key"):
            st.error("Укажите API Key в настройках!")
        else:
            cl = get_ai_client(cfg["api_key"], cfg["base_url"])
            m_name = cfg["model_name"]
            
            with st.status("Многоагентный ИИ-конвейер обрабатывает ход...", expanded=True) as status:
                hist_item = {k: copy.deepcopy(v) for k, v in st.session_state.items() if not k.startswith(UI_KEYS) and k not in ["history"]}
                st.session_state.history.append(hist_item)
                
                common_state = {
                    "turn": st.session_state.turn,
                    "current_date": st.session_state.current_date,
                    "player_country": st.session_state.player_country,
                    "difficulty": st.session_state.difficulty,
                    "solar_activity": st.session_state.solar_activity,
                    "my_country": st.session_state.countries[st.session_state.player_country],
                    "countries": st.session_state.countries,
                    "military_mod_requests": st.session_state.military_mod_requests
                }
                
                turn_tokens = 0
                
                st.write("1/4 Внутренний арбитр оценивает указы и повестку дня...")
                res_internal, t1 = agent_internal_arbiter(cl, m_name, common_state, orders_current)
                turn_tokens += t1
                
                st.write("2/4 Мировой симулятор рассчитывает время и действия держав...")
                res_world, t2 = agent_world_simulator(cl, m_name, common_state, orders_current)
                turn_tokens += t2
                
                st.write("3/4 Дипломатический корпус готовит депеши и ответы...")
                res_diplo, t3 = agent_diplomacy(cl, m_name, common_state, st.session_state.pending_diplo)
                turn_tokens += t3
                
                st.write("4/4 Главный архитектор обновляет ВПК и границы...")
                res_arch, t4 = agent_world_architect(cl, m_name, common_state)
                turn_tokens += t4
                
                status.update(label="Ход успешно обработан!", state="complete")

            st.session_state.token_usage["turn"] = turn_tokens
            st.session_state.token_usage["total"] += turn_tokens
            
            if res_world.get("new_date"):
                st.session_state.current_date = res_world["new_date"]
                
            st.session_state.turn_archives.append({
                "turn": st.session_state.turn + 1,
                "date": st.session_state.current_date,
                "world_events": res_world.get("new_world_events", []),
                "flavor_events": res_world.get("flavor_events", []),
                "player_events": res_internal.get("new_player_events", []),
                "press_excerpt": res_internal.get("press_excerpt")
            })
            
            my_c = st.session_state.countries[st.session_state.player_country]
            if "updated_stats" in res_internal:
                my_c["stats"].update(res_internal["updated_stats"])
            if "updated_issues" in res_internal:
                my_c["current_issues"] = res_internal["updated_issues"]
            st.session_state.internal_events = res_internal.get("new_internal_events", [])
            
            if "diplo_responses" in res_diplo:
                for d_resp in res_diplo["diplo_responses"]:
                    f_c, t_c = d_resp["from"], d_resp["to"]
                    c_key = f"{min(f_c, t_c)}-{max(f_c, t_c)}"
                    if c_key not in st.session_state.chats: st.session_state.chats[c_key] = []
                    st.session_state.chats[c_key].append({"from": f_c, "text": d_resp["message"]})
                    if f_c != st.session_state.player_country:
                        st.session_state.unread_messages.add(f_c)
                        
            if "new_tenders" in res_arch:
                st.session_state.military_tenders.extend(res_arch["new_tenders"])
            st.session_state.military_mod_requests = []
            
            if "country_transformations" in res_arch:
                for trans in res_arch["country_transformations"]:
                    hide_c = trans.get("hide_country")
                    if hide_c and hide_c in st.session_state.countries:
                        st.session_state.countries[hide_c]["status"] = "Спящая"
                    for sp in trans.get("spawn_countries", []):
                        sp_name = sp["name"]
                        st.session_state.countries[sp_name] = {
                            "status": "Активная",
                            "is_great_power": sp.get("is_great_power", False),
                            "regime": sp.get("regime", "Временное правительство"),
                            "faction": "Нет", "overlord": None,
                            "resources": "Ограниченные резервы",
                            "stats": sp.get("stats", {"stability": 50, "war_support": 70, "military_readiness": 50, "manpower_approx": "~300 тыс. чел."}),
                            "current_issues": [{"name": "Гражданская война", "start_date": st.session_state.current_date, "target_date": "1 Год", "status": "Острая фаза"}],
                            "relations": {},
                            "military": get_smart_fallback_military(sp_name, st.session_state.current_date)
                        }
                        if hide_c:
                            old_k = f"{min(st.session_state.player_country, hide_c)}-{max(st.session_state.player_country, hide_c)}"
                            new_k = f"{min(st.session_state.player_country, sp_name)}-{max(st.session_state.player_country, sp_name)}"
                            st.session_state.chats[new_k] = copy.deepcopy(st.session_state.chats.get(old_k, []))

            st.session_state.pending_diplo = []
            st.session_state.turn += 1
            
            if st.session_state.turn % st.session_state.autosave_interval == 0:
                save_game_to_slot(st.session_state.current_slot)
                
            st.rerun()
