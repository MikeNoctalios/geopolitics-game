import streamlit as st
import json
import os
import copy
from openai import OpenAI

# ==========================================
# 0. СИСТЕМНЫЕ ПАПКИ И НАСТРОЙКИ
# ==========================================
CONFIG_FILE = "config.json"
SAVES_DIR = "saves"
SCENARIOS_DIR = "scenarios"

for d in [SAVES_DIR, SCENARIOS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"api_key": "", "base_url": "", "model_name": "gpt-4o-mini"}

def save_config(api_key, base_url, model_name):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key, "base_url": base_url, "model_name": model_name}, f)

# ==========================================
# 1. ЛОГИКА СОХРАНЕНИЙ И ИНИЦИАЛИЗАЦИИ
# ==========================================
def get_save_info(slot):
    path = os.path.join(SAVES_DIR, f"save_{slot}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return f"{data.get('player_country', 'Неизвестно')} | Ход: {data.get('turn', 1)} | Дата: {data.get('current_date', '')}"
        except json.JSONDecodeError:
            return "Повреждённое сохранение"
    return "Пустая ячейка"

def load_game(slot):
    path = os.path.join(SAVES_DIR, f"save_{slot}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in data.items():
                st.session_state[k] = v
            
            if "unread_messages" in st.session_state and isinstance(st.session_state.unread_messages, list):
                st.session_state.unread_messages = set(st.session_state.unread_messages)
                
            st.session_state.current_slot = slot
            st.session_state.in_game = True
    except json.JSONDecodeError:
        st.error("Ошибка загрузки: файл сохранения повреждён.")

def save_game():
    if "current_slot" in st.session_state:
        path = os.path.join(SAVES_DIR, f"save_{st.session_state.current_slot}.json")
        save_data = {}
        for k, v in st.session_state.items():
            if not k.startswith(("orders_", "diplo_", "current_diplo_target", "chat_")) and k != "history":
                if isinstance(v, set):
                    save_data[k] = list(v)
                else:
                    save_data[k] = v
                    
        with open(path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False)

def delete_save(slot):
    path = os.path.join(SAVES_DIR, f"save_{slot}.json")
    if os.path.exists(path): os.remove(path)

def start_new_game(slot, scenario_file, country):
    with open(os.path.join(SCENARIOS_DIR, scenario_file), "r", encoding="utf-8") as f:
        scen = json.load(f)
    
    st.session_state.clear()
    st.session_state.in_game = True
    st.session_state.current_slot = slot
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
    save_game()

def rollback_turn():
    if st.session_state.history:
        last_state = st.session_state.history.pop()
        for k, v in last_state.items():
            st.session_state[k] = v
        save_game()
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
    
    ВАЖНОЕ ПРАВИЛО: В "new_world_events" добавляй ТОЛЬКО публично известные новости! Тайные действия (шпионаж, секретные договоры, тайное перевооружение) НЕ должны попадать в мировые новости, пока их не раскроют. О тайных успехах/провалах самого игрока пиши лично ему в "new_player_events".
    
    Верни ТОЛЬКО JSON:
    {
      "new_date": "<Новая дата, например 'Апрель 1935'>",
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
    В diplo_responses ИИ-страны могут писать игроку первыми, предлагать идеи или выдвигать требования.
    Удаляй старые решенные current_issues и добавляй новые.
    Без markdown, только сырой JSON.
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

if "menu_stage" not in st.session_state:
    st.session_state.menu_stage = 1

# --- ГЛАВНОЕ МЕНЮ (МНОГОСТАДИЙНОЕ) ---
if "in_game" not in st.session_state or not st.session_state.in_game:
    st.title("🌍 Geopolitics AI")
    
    # СТАДИЯ 1: Ячейки и Настройки
    if st.session_state.menu_stage == 1:
        with st.expander("⚙️ Настройки API", expanded=True):
            cfg_api = st.text_input("API Key", value=cfg.get("api_key", ""), type="password")
            cfg_url = st.text_input("Base URL", value=cfg.get("base_url", ""))
            cfg_mod = st.text_input("Model Name", value=cfg.get("model_name", "gpt-4o-mini"))
                
            if st.button("Сохранить настройки"):
                save_config(cfg_api, cfg_url, cfg_mod)
                st.success("Сохранено!")
                st.rerun()

        st.subheader("Меню сохранений")
        col1, col2, col3 = st.columns(3)
        for i, col in enumerate([col1, col2, col3], 1):
            with col:
                st.card_title = f"Ячейка {i}"
                info = get_save_info(i)
                
                if info == "Повреждённое сохранение":
                    st.error(f"**{st.card_title}**\n\n{info}")
                elif info != "Пустая ячейка":
                    st.info(f"**{st.card_title}**\n\n{info}")
                else:
                    st.success(f"**{st.card_title}**\n\n{info}")
                
                if info not in ["Пустая ячейка", "Повреждённое сохранение"]:
                    if st.button(f"Загрузить {i}", key=f"load_{i}", use_container_width=True):
                        load_game(i)
                        st.rerun()
                        
                if info != "Пустая ячейка":
                    if st.button(f"Удалить {i}", key=f"del_{i}", type="secondary", use_container_width=True):
                        delete_save(i)
                        st.rerun()
                else:
                    if st.button(f"Новая игра", key=f"new_{i}", type="primary", use_container_width=True):
                        st.session_state.target_slot = i
                        st.session_state.menu_stage = 2
                        st.rerun()
        st.stop()

    # СТАДИЯ 2: Выбор сценария
    elif st.session_state.menu_stage == 2:
        st.subheader("Шаг 1: Выбор сценария")
        if st.button("⬅️ Назад к сохранениям"):
            st.session_state.menu_stage = 1
            st.rerun()
            
        scenarios = [f for f in os.listdir(SCENARIOS_DIR) if f.endswith('.json')]
        if not scenarios:
            st.error("В папке scenarios/ нет ни одного сценария!")
            st.stop()
            
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
        st.stop()

    # СТАДИЯ 3: Выбор страны
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
                start_new_game(st.session_state.target_slot, st.session_state.selected_scenario, selected_country)
                st.session_state.menu_stage = 1 
                st.rerun()
        st.stop()

# --- ИГРОВОЙ ИНТЕРФЕЙС ---
with st.sidebar:
    st.header("Панель управления")
    if st.button("💾 Сохранить и выйти в меню"):
        save_game()
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
    
    # ВОССТАНОВЛЕНО ДОСЬЕ В ДИПЛОМАТИИ
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
                save_game() 
                st.rerun()