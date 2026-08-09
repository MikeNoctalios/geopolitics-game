import streamlit as st
import json
import os
import copy
from openai import OpenAI

# ==========================================
# 0. СИСТЕМНЫЕ ПАПКИ И НАСТРОЙКИ (Абсолютные пути)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SAVES_DIR = os.path.join(BASE_DIR, "saves")
SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios")

for d in [SAVES_DIR, SCENARIOS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# Автогенерация базового сценария, если папка пуста (защита от ошибок GitHub)
if not os.listdir(SCENARIOS_DIR):
    fallback_scenario = {
        "name": "1935: Базовый сценарий (Автогенерация)",
        "description": "Сгенерировано автоматически, так как папка сценариев была пуста.",
        "start_date": "1 Января 1935",
        "world_events": [{"turn": 1, "title": "Начало", "desc": "Мир замер в ожидании.", "type": "public"}],
        "countries": {
            "Великобритания": {
                "status": "Активная", "is_great_power": True, "regime": "Демократия", "faction": "Союзники", "overlord": None,
                "stats": {"stability": 80, "war_support": 15, "military_readiness": 45},
                "profile": "Морская гегемония.", "current_issues": [{"name": "Экономика", "status": "В процессе", "eta": "Годы"}],
                "relations": {}
            },
            "Германия": {
                "status": "Активная", "is_great_power": True, "regime": "Национал-социализм", "faction": "Нет", "overlord": None,
                "stats": {"stability": 85, "war_support": 60, "military_readiness": 35},
                "profile": "Ревизионизм.", "current_issues": [{"name": "Перевооружение", "status": "Тайное", "eta": "Годы"}],
                "relations": {}
            }
        }
    }
    with open(os.path.join(SCENARIOS_DIR, "1935_fallback.json"), "w", encoding="utf-8") as f:
        json.dump(fallback_scenario, f, ensure_ascii=False, indent=4)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"api_key": "", "base_url": "", "model_name": "gpt-4o-mini", "theme": "Светлая (по умолчанию)"}

def save_config(api_key, base_url, model_name, theme):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key, "base_url": base_url, "model_name": model_name, "theme": theme}, f)

def apply_theme(theme_name):
    themes = {
        "Тёмная": "{background-color: #1e1e1e; color: #f0f0f0;}",
        "Светлая (по умолчанию)": "",
        "Серая": "{background-color: #7f8c8d; color: #ffffff;}",
        "Пустынная": "{background-color: #e6d5b8; color: #3e2723;}",
        "Яркая зелёная": "{background-color: #a8e6cf; color: #1b4332;}",
        "Тёмная зелёная": "{background-color: #1b4332; color: #d8f3dc;}",
        "Синяя": "{background-color: #1a365d; color: #e2e8f0;}"
    }
    css = themes.get(theme_name, "")
    if css:
        st.markdown(f"<style>.stApp {css} .stSidebar {css}</style>", unsafe_allow_html=True)

# ==========================================
# 1. ЛОГИКА СОХРАНЕНИЙ (ФАЙЛОВАЯ)
# ==========================================
def get_save_data_str():
    save_data = {}
    for k, v in st.session_state.items():
        if not k.startswith(("orders_", "diplo_", "current_diplo_target", "chat_", "uploaded_save")) and k != "history":
            if isinstance(v, set):
                save_data[k] = list(v)
            else:
                save_data[k] = v
    return json.dumps(save_data, ensure_ascii=False, indent=2)

def load_game_from_file(uploaded_file):
    try:
        data = json.load(uploaded_file)
        for k, v in data.items():
            st.session_state[k] = v
        if "unread_messages" in st.session_state and isinstance(st.session_state.unread_messages, list):
            st.session_state.unread_messages = set(st.session_state.unread_messages)
        st.session_state.in_game = True
        return True
    except Exception as e:
        st.error(f"Ошибка загрузки сохранения. Возможно, файл повреждён. Детали: {e}")
        return False

def start_new_game(scenario_file, country):
    with open(os.path.join(SCENARIOS_DIR, scenario_file), "r", encoding="utf-8") as f:
        scen = json.load(f)
    
    keys_to_keep = ["menu_stage", "selected_scenario"]
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]
            
    st.session_state.in_game = True
    st.session_state.turn = 1
    st.session_state.current_date = scen["start_date"]
    st.session_state.player_country = country
    st.session_state.world_events = scen["world_events"]
    st.session_state.player_events = []
    st.session_state.countries = scen["countries"]
    st.session_state.countries[country]["status"] = "Активная"
    
    st.session_state.chats = {}
    st.session_state.unread_messages = set()
    st.session_state.advisor_chats = {
        "internal": [{"role": "assistant", "content": "Господин, я отвечаю за стабильность, экономику и реформы внутри страны."}],
        "foreign": [{"role": "assistant", "content": "Мое ведомство следит за дипломатией, альянсами и мировой ареной."}],
        "defense": [{"role": "assistant", "content": "Армия и флот ждут ваших приказов. Докладываю о военной готовности."}]
    }
    st.session_state.notes = ""
    st.session_state.pending_diplo = []
    st.session_state.meta_instructions = ""
    st.session_state.history = []

def rollback_turn():
    if st.session_state.get("history"):
        last_state = st.session_state.history.pop()
        for k, v in last_state.items():
            st.session_state[k] = v
        return True
    return False

# ==========================================
# 2. ИИ-ФУНКЦИИ (ГЕЙММАСТЕР И СОВЕТНИКИ)
# ==========================================
def get_ai_client(api_key, base_url):
    client_kwargs = {"api_key": api_key if api_key else "dummy-key"}
    if base_url: client_kwargs["base_url"] = base_url
    return OpenAI(**client_kwargs)

def process_turn(api_key, base_url, model_name, player_orders, diplo_messages):
    client = get_ai_client(api_key, base_url)
    
    system_prompt = """
    Ты ИИ-гейммастер. Симулируй мир, учитывая действия игрока и великих держав.
    Ход времени динамический: если событий мало, проматывай на 2-4 месяца. Если война/кризис - на 1-3 недели.
    
    ВАЖНОЕ ПРАВИЛО: В "new_world_events" добавляй ТОЛЬКО публично известные новости! Тайные действия НЕ должны попадать в мировые новости. О тайных успехах/провалах игрока пиши лично ему в "new_player_events".
    
    Верни ТОЛЬКО JSON:
    {
      "new_date": "<Новая дата>",
      "new_world_events": [{"turn": <int>, "title": "<str>", "desc": "<str>", "type": "public"}],
      "new_player_events": [{"turn": <int>, "title": "<str>", "desc": "<str>"}],
      "updated_countries": {
         "Имя_страны": {
             "stats": {"stability": <int>, "war_support": <int>, "military_readiness": <int>},
             "current_issues": [{"name": "<str>", "status": "<str>", "eta": "<str>"}],
             "relations": {"<str>": "<str>"},
             "regime": "<str>", "faction": "<str>", "overlord": "<str или null>"
         }
      },
      "diplo_responses": [{"from": "<str>", "to": "<str>", "message": "<str>"}]
    }
    В diplo_responses ИИ-страны могут писать игроку первыми. Удаляй решенные current_issues и добавляй новые. Без markdown.
    """
    
    state_for_ai = {
        "turn": st.session_state.turn,
        "current_date": st.session_state.current_date,
        "player_country": st.session_state.player_country,
        "world_events": st.session_state.world_events[-3:], 
        "countries": {k: v for k, v in st.session_state.countries.items() if v["status"] != "Спящая"},
        "player_orders": player_orders,
        "new_diplo_messages": diplo_messages,
        "meta_instructions_from_player": st.session_state.meta_instructions
    }
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(state_for_ai, ensure_ascii=False)}
            ],
            temperature=0.4
        )
        raw_content = response.choices[0].message.content.strip()
        if raw_content.startswith("```json"): raw_content = raw_content[7:]
        if raw_content.startswith("```"): raw_content = raw_content[3:]
        if raw_content.endswith("```"): raw_content = raw_content[:-3]
        return json.loads(raw_content.strip())
    except Exception as e:
        return {"error": str(e)}

def ask_advisor_ai(api_key, base_url, model_name, role, user_question):
    client = get_ai_client(api_key, base_url)
    stats = st.session_state.countries[st.session_state.player_country]
    
    role_desc = {
        "internal": "Министр внутренних дел (Экономика, реформы, стабильность, общество).",
        "foreign": "Министр иностранных дел (Дипломатия, пакты, шпионаж, отношения).",
        "defense": "Министр обороны (Армия, флот, война, производство оружия)."
    }
    sys_prompt = f"""Ты - {role_desc[role]} страны {st.session_state.player_country}. 
    Дата: {st.session_state.current_date}. Стабильность: {stats['stats']['stability']}, Армия: {stats['stats']['military_readiness']}.
    Проблемы: {', '.join([i['name'] for i in stats.get('current_issues', [])])}.
    Отвечай только по своей специализации. Давай конкретные советы."""
    
    messages = [{"role": "system", "content": sys_prompt}]
    for msg in st.session_state.advisor_chats[role][-4:]:
        messages.append(msg)
    messages.append({"role": "user", "content": user_question})
    
    try:
        resp = client.chat.completions.create(model=model_name, messages=messages, temperature=0.7)
        return resp.choices[0].message.content
    except Exception as e:
        return f"[Ошибка: {str(e)}]"

# ==========================================
# 3. ИНТЕРФЕЙС И РЕНДЕР
# ==========================================
st.set_page_config(page_title="Geopolitics AI", layout="wide")
cfg = load_config()
apply_theme(cfg.get("theme", "Светлая (по умолчанию)"))

if "menu_stage" not in st.session_state:
    st.session_state.menu_stage = 1

# --- ГЛАВНОЕ МЕНЮ ---
if "in_game" not in st.session_state or not st.session_state.in_game:
    st.title("🌍 Geopolitics AI")
    
    if st.session_state.menu_stage == 1:
        with st.expander("⚙️ Настройки API и Темы", expanded=True):
            col_cfg1, col_cfg2 = st.columns(2)
            with col_cfg1:
                cfg_api = st.text_input("API Key", value=cfg.get("api_key", ""), type="password")
                cfg_url = st.text_input("Base URL", value=cfg.get("base_url", ""))
                cfg_mod = st.text_input("Model Name", value=cfg.get("model_name", "gpt-4o-mini"))
            with col_cfg2:
                theme_list = ["Светлая (по умолчанию)", "Тёмная", "Серая", "Пустынная", "Яркая зелёная", "Тёмная зелёная", "Синяя"]
                cfg_theme = st.selectbox("Визуальная тема", theme_list, index=theme_list.index(cfg.get("theme", "Светлая (по умолчанию)")))
                
            if st.button("Сохранить настройки"):
                save_config(cfg_api, cfg_url, cfg_mod, cfg_theme)
                st.success("Сохранено! (Тема применится сразу)")
                st.rerun()

        st.divider()
        col_menu1, col_menu2 = st.columns(2)
        
        with col_menu1:
            st.subheader("Начать новую игру")
            if st.button("🚀 Выбрать сценарий", type="primary", use_container_width=True):
                st.session_state.menu_stage = 2
                st.rerun()
                
        with col_menu2:
            st.subheader("Продолжить игру")
            uploaded_save = st.file_uploader("Загрузите файл сохранения (.json)", type=["json"], key="file_uploader")
            if uploaded_save is not None:
                if st.button("📥 Загрузить сохранение", use_container_width=True):
                    if load_game_from_file(uploaded_save):
                        st.rerun()

    # Выбор сценария
    elif st.session_state.menu_stage == 2:
        st.subheader("Шаг 1: Выбор сценария")
        if st.button("⬅️ Назад в главное меню"):
            st.session_state.menu_stage = 1
            st.rerun()
            
        scenarios = [f for f in os.listdir(SCENARIOS_DIR) if f.endswith('.json')]
        
        for scen_file in scenarios:
            with open(os.path.join(SCENARIOS_DIR, scen_file), "r", encoding="utf-8") as f:
                scen_data = json.load(f)
                
            with st.container(border=True):
                st.markdown(f"### {scen_data.get('name', scen_file)}")
                st.write(f"**Дата старта:** {scen_data.get('start_date', 'Неизвестно')}")
                st.write(f"**Количество стран:** {len(scen_data.get('countries', {}))}")
                st.write(f"**Описание:** {scen_data.get('description', 'Нет описания')}")
                if st.button(f"Выбрать этот сценарий", key=f"sel_{scen_file}"):
                    st.session_state.selected_scenario = scen_file
                    st.session_state.menu_stage = 3
                    st.rerun()
                    
        st.divider()
        st.subheader("🛠 Создание и загрузка сценариев")
        
        # ШАБЛОН ДЛЯ СКАЧИВАНИЯ
        template_data = {
            "name": "Мой кастомный сценарий",
            "description": "Описание сценария...",
            "start_date": "1 Сентября 1939",
            "world_events": [{"turn": 1, "title": "Начало", "desc": "Мир изменился.", "type": "public"}],
            "countries": {
                "Моя Страна": {
                    "status": "Активная", "is_great_power": True, "regime": "Республика", "faction": "Нет", "overlord": None,
                    "stats": {"stability": 50, "war_support": 50, "military_readiness": 50},
                    "profile": "Описание страны.", "current_issues": [{"name": "Проблема", "status": "Активно", "eta": "1 год"}],
                    "relations": {"Другая Страна": "Враждебность"}
                },
                "Другая Страна": {
                    "status": "Спящая", "is_great_power": False, "regime": "Монархия", "faction": "Нет", "overlord": None,
                    "stats": {"stability": 30, "war_support": 20, "military_readiness": 10},
                    "profile": "Минор.", "current_issues": [], "relations": {}
                }
            }
        }
        st.download_button(
            label="📝 Скачать шаблон сценария (.json)",
            data=json.dumps(template_data, ensure_ascii=False, indent=4),
            file_name="scenario_template.json",
            mime="application/json"
        )
        
        # ЗАГРУЗКА КАСТОМНОГО СЦЕНАРИЯ
        uploaded_scen = st.file_uploader("Загрузить готовый сценарий", type=["json"], key="scen_uploader")
        if uploaded_scen:
            try:
                custom_scen_data = json.load(uploaded_scen)
                file_path = os.path.join(SCENARIOS_DIR, uploaded_scen.name)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(custom_scen_data, f, ensure_ascii=False, indent=4)
                st.success(f"Сценарий {uploaded_scen.name} успешно загружен! Обновите страницу или выберите его в списке выше.")
            except Exception as e:
                st.error(f"Ошибка загрузки сценария: {e}")

    # Выбор страны
    elif st.session_state.menu_stage == 3:
        st.subheader("Шаг 2: Выбор страны")
        if st.button("⬅️ К списку сценариев"):
            st.session_state.menu_stage = 2
            st.rerun()
            
        with open(os.path.join(SCENARIOS_DIR, st.session_state.selected_scenario), "r", encoding="utf-8") as f:
            scen_data = json.load(f)
            
        countries = scen_data.get("countries", {})
        great_powers = sorted([c for c, d in countries.items() if d.get("is_great_power")])
        minors = sorted([c for c, d in countries.items() if not d.get("is_great_power")])
        
        selected_country = st.selectbox("Доступные страны", ["-- Выберите страну --"] + great_powers + ["---"] + minors)
        
        if selected_country and selected_country not in ["-- Выберите страну --", "---"]:
            c_data = countries[selected_country]
            st.markdown(f"### Досье: {selected_country}")
            st.write(f"**Профиль:** {c_data.get('profile', '')}")
            st.write(f"**Режим:** {c_data.get('regime', '')} | **Фракция:** {c_data.get('faction', 'Нет')}")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Стабильность", f"{c_data.get('stats', {}).get('stability', 0)}/100")
            c2.metric("Поддержка войны", f"{c_data.get('stats', {}).get('war_support', 0)}/100")
            c3.metric("Боеготовность", f"{c_data.get('stats', {}).get('military_readiness', 0)}/100")
            
            if st.button("🚀 Начать кампанию", type="primary", use_container_width=True):
                start_new_game(st.session_state.selected_scenario, selected_country)
                st.session_state.menu_stage = 1 
                st.rerun()
    st.stop()

# --- ИГРОВОЙ ИНТЕРФЕЙС ---
with st.sidebar:
    st.header("Управление игрой")
    
    save_str = get_save_data_str()
    st.download_button(
        label="📥 Скачать сохранение",
        data=save_str,
        file_name=f"save_turn_{st.session_state.turn}.json",
        mime="application/json",
        use_container_width=True,
        type="primary"
    )
    
    if st.button("🚪 Выйти в главное меню", use_container_width=True):
        st.session_state.in_game = False
        st.rerun()
        
    st.divider()
    st.subheader("📝 Заметки")
    st.session_state.notes = st.text_area("Личный блокнот", st.session_state.notes, height=200)
    
    st.divider()
    st.subheader("🛠 Debug / Гейммастер")
    with st.expander("Инструменты"):
        st.session_state.meta_instructions = st.text_area("Указания гейммастеру (правила, канон):", st.session_state.meta_instructions)
        if st.button("↩️ Откатить ход"):
            if rollback_turn():
                st.success("Ход откачен!")
                st.rerun()
            else:
                st.error("Нет истории для отката.")

st.title(f"Ход {st.session_state.turn} | {st.session_state.current_date}")
st.markdown(f"**Игра за:** {st.session_state.player_country}")

tab_news, tab_country, tab_diplo, tab_advisor = st.tabs(["📰 Новости", "🏛 Управление", "🤝 Дипломатия", "🧠 Советники"])

with tab_news:
    col_w, col_p = st.columns(2)
    with col_w:
        st.header("Мировая арена")
        for event in reversed(st.session_state.world_events):
            st.info(f"**[{event.get('date', f'Ход {event.get('turn')}')}] {event['title']}**\n\n{event['desc']}")
    with col_p:
        st.header("О вас")
        if not st.session_state.player_events:
            st.write("Пока нет специфических новостей.")
        for event in reversed(st.session_state.player_events):
            st.success(f"**[{event.get('date', f'Ход {event.get('turn')}')}] {event['title']}**\n\n{event['desc']}")

with tab_country:
    my_country = st.session_state.countries[st.session_state.player_country]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Стабильность", f"{my_country['stats']['stability']}/100")
    c2.metric("Поддержка войны", f"{my_country['stats']['war_support']}/100")
    c3.metric("Готовность армии", f"{my_country['stats']['military_readiness']}/100")
    
    st.subheader("Повестка дня и процессы")
    if not my_country.get('current_issues'):
        st.write("Нет активных процессов.")
    else:
        for issue in my_country['current_issues']:
            st.warning(f"📌 **{issue['name']}** | Статус: *{issue['status']}* | Осталось: {issue['eta']}")
        
    st.subheader("Приказы на текущий ход")
    orders_key = f"orders_{st.session_state.turn}"
    st.text_area("Опишите политические, экономические или военные решения:", key=orders_key, height=150)

with tab_diplo:
    if st.session_state.unread_messages:
        st.error(f"📩 У вас новые сообщения от: {', '.join(st.session_state.unread_messages)}")
        
    def format_country_label(c):
        label = c
        c_data = st.session_state.countries[c]
        if c_data.get("overlord"): label += f" ({c_data['overlord']})"
        if c in st.session_state.unread_messages: label += " 📩"
        return label

    target_country = st.selectbox(
        "Выберите страну для связи:", 
        options=[c for c in sorted(st.session_state.countries.keys()) if c != st.session_state.player_country],
        format_func=format_country_label,
        key="diplo_target_selectbox"
    )
    
    if target_country in st.session_state.unread_messages:
        st.session_state.unread_messages.remove(target_country)
    
    target_data = st.session_state.countries[target_country]
    
    with st.expander(f"Досье: {target_country}", expanded=True):
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.write(f"**Режим:** {target_data.get('regime', 'Неизвестно')}")
            st.write(f"**Фракция:** {target_data.get('faction', 'Нет')}")
            st.write(f"**Отношение к нам:** {target_data.get('relations', {}).get(st.session_state.player_country, 'Нейтральное')}")
        with col_d2:
            rel = target_data.get('relations', {}).get(st.session_state.player_country, "")
            if rel in ["Союзник", "Дружелюбие", "Гарантия"]:
                st.write(f"**Военный потенциал:** {target_data.get('stats', {}).get('military_readiness', 0)}/100 (Точно)")
                st.write(f"**Стабильность:** {target_data.get('stats', {}).get('stability', 0)}/100 (Точно)")
            else:
                mil_approx = target_data.get('stats', {}).get('military_readiness', 50)
                st.write(f"**Военный потенциал:** {max(0, mil_approx-10)} - {min(100, mil_approx+10)} (Оценка)")
                
        recent_events = [e for e in st.session_state.world_events if target_country in e.get('desc', '') or target_country in e.get('title', '')]
        if recent_events:
            st.markdown("**Связанные недавние события:**")
            for e in recent_events[-2:]:
                st.caption(f"- {e['title']}")
                
    chat_key = f"{min(st.session_state.player_country, target_country)}-{max(st.session_state.player_country, target_country)}"
    if chat_key not in st.session_state.chats:
        st.session_state.chats[chat_key] = []
        
    st.subheader(f"Переписка: {target_country}")
    for msg in st.session_state.chats[chat_key]:
        if msg["from"] == st.session_state.player_country:
            st.markdown(f"<div style='text-align: right; color: #4CAF50; padding: 5px;'><b>Вы:</b> {msg['text']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align: left; color: #2196F3; padding: 5px;'><b>{msg['from']}:</b> {msg['text']}</div>", unsafe_allow_html=True)
        st.divider()
            
    def send_diplo():
        msg = st.session_state.diplo_input
        if msg and target_country:
            st.session_state.chats[chat_key].append({"from": st.session_state.player_country, "text": msg})
            st.session_state.pending_diplo.append({"from": st.session_state.player_country, "to": target_country, "text": msg})
            st.session_state.diplo_input = ""
            
    st.text_area("Ваше сообщение:", key="diplo_input", height=100)
    st.button("Отправить депешу", on_click=send_diplo, type="secondary")

with tab_advisor:
    adv_tabs = st.tabs(["Внутренние дела", "Иностранные дела", "Министерство обороны"])
    roles = ["internal", "foreign", "defense"]
    
    for i, role in enumerate(roles):
        with adv_tabs[i]:
            for msg in st.session_state.advisor_chats[role]:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
            
            if prompt := st.chat_input("Спросите министра...", key=f"chat_{role}"):
                st.session_state.advisor_chats[role].append({"role": "user", "content": prompt})
                st.rerun()

            if st.session_state.advisor_chats[role][-1]["role"] == "user":
                with st.spinner("Министр готовит доклад..."):
                    ans = ask_advisor_ai(cfg["api_key"], cfg["base_url"], cfg["model_name"], role, st.session_state.advisor_chats[role][-1]["content"])
                    st.session_state.advisor_chats[role].append({"role": "assistant", "content": ans})
                    st.rerun()

st.divider()
col_b1, col_b2, col_b3 = st.columns([1,2,1])
with col_b2:
    if st.button("⏭ ЗАВЕРШИТЬ ХОД", use_container_width=True, type="primary"):
        with st.spinner("Гейммастер симулирует мир..."):
            history_state = {k: copy.deepcopy(v) for k, v in st.session_state.items() if not k.startswith("orders_") and k != "history"}
            st.session_state.history.append(history_state)
            
            current_orders = st.session_state.get(f"orders_{st.session_state.turn}", "")
            
            ai_response = process_turn(
                cfg["api_key"], cfg["base_url"], cfg["model_name"],
                player_orders=current_orders, 
                diplo_messages=st.session_state.pending_diplo
            )
            
            if "error" in ai_response:
                st.error(f"Ошибка ИИ: {ai_response['error']}")
                st.session_state.history.pop()
            else:
                if "new_date" in ai_response:
                    st.session_state.current_date = ai_response["new_date"]
                
                if "new_world_events" in ai_response:
                    for ev in ai_response["new_world_events"]:
                        ev["turn"] = st.session_state.turn + 1
                        ev["date"] = st.session_state.current_date
                        st.session_state.world_events.append(ev)
                        
                if "new_player_events" in ai_response:
                    for ev in ai_response["new_player_events"]:
                        ev["turn"] = st.session_state.turn + 1
                        ev["date"] = st.session_state.current_date
                        st.session_state.player_events.append(ev)
                
                if "updated_countries" in ai_response:
                    for c_name, c_data in ai_response["updated_countries"].items():
                        if c_name in st.session_state.countries:
                            st.session_state.countries[c_name]["stats"].update(c_data.get("stats", {}))
                            st.session_state.countries[c_name]["current_issues"] = c_data.get("current_issues", [])
                            st.session_state.countries[c_name]["relations"].update(c_data.get("relations", {}))
                            if "regime" in c_data: st.session_state.countries[c_name]["regime"] = c_data["regime"]
                            if "faction" in c_data: st.session_state.countries[c_name]["faction"] = c_data["faction"]
                            if "overlord" in c_data: st.session_state.countries[c_name]["overlord"] = c_data["overlord"]
                            st.session_state.countries[c_name]["status"] = "Активная"
                
                if "diplo_responses" in ai_response:
                    for resp in ai_response["diplo_responses"]:
                        c_key = f"{min(resp['from'], resp['to'])}-{max(resp['from'], resp['to'])}"
                        if c_key not in st.session_state.chats:
                            st.session_state.chats[c_key] = []
                        st.session_state.chats[c_key].append({"from": resp["from"], "text": resp["message"]})
                        st.session_state.unread_messages.add(resp["from"])
                
                stats = st.session_state.countries[st.session_state.player_country]["stats"]
                if stats["stability"] < 40:
                    st.session_state.advisor_chats["internal"].append({"role": "assistant", "content": "⚠️ Внимание! Стабильность критически низка. Возможны бунты. Срочно примите меры."})
                if stats["military_readiness"] < 30 and stats["war_support"] > 50:
                    st.session_state.advisor_chats["defense"].append({"role": "assistant", "content": "⚠️ Народ хочет войны, но армия не готова! Нужно финансирование вооруженных сил."})
                
                st.session_state.pending_diplo = []
                st.session_state.turn += 1
                st.rerun()
