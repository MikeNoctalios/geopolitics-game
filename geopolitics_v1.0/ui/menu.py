import os
import json
import streamlit as st
from ai.client import load_config, save_config
from core.state import SCENARIOS_DIR, get_slot_path, get_slot_info, load_game_from_slot, delete_slot
from core.time_system import extract_year
from core.military import ensure_military_loaded

def start_new_game_session(slot_id, scenario_file, country, difficulty, solar_activity, is_alt_history):
    with open(os.path.join(SCENARIOS_DIR, scenario_file), "r", encoding="utf-8") as f:
        scen = json.load(f)
        
    st.session_state.clear()
    st.session_state.in_game = True
    st.session_state.current_slot = slot_id
    st.session_state.scenario_file = scenario_file
    st.session_state.scenario_name = scen.get("name", scenario_file)
    st.session_state.turn = 1
    st.session_state.current_date = scen.get("start_date", "1 Января 1935")
    st.session_state.player_country = country
    st.session_state.difficulty = difficulty
    st.session_state.solar_activity = solar_activity
    st.session_state.is_alt_history = is_alt_history
    st.session_state.alarm_clock_active = False
    st.session_state.ongoing_arcs = [f"Начало кампании {st.session_state.current_date}"]
    
    st.session_state.turn_archives = [{
        "turn": 1,
        "date": st.session_state.current_date,
        "player_orders_raw": "Старт сценария",
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
    st.session_state.military_mod_requests = []
    st.session_state.rd_projects = []
    
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
    from core.state import save_game_to_slot
    save_game_to_slot(slot_id)

def render_main_menu():
    cfg = load_config()
    st.title("🌍 Geopolitics AI Engine (Alpha)")
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
            
        raw_scen_files = [f for f in os.listdir(SCENARIOS_DIR) if f.endswith('.json')]
        scen_meta_list = []
        for sf in raw_scen_files:
            try:
                with open(os.path.join(SCENARIOS_DIR, sf), "r", encoding="utf-8") as f:
                    sd = json.load(f)
                    start_d = sd.get("start_date", "1935")
                    year = extract_year(start_d)
                    total_c = len(sd.get("countries", {}))
                    has_ctx = bool(sd.get("world_context") or sd.get("world_context_file"))
                    # Автоопределение alt-history для обратной совместимости
                    is_alt = sd.get("is_alt_history", has_ctx)
                    scen_meta_list.append({
                        "file": sf,
                        "name": sd.get("name", sf),
                        "start_date": start_d,
                        "year": year,
                        "count": total_c,
                        "is_alt_history": is_alt,
                        "data": sd
                    })
            except Exception: continue
                
        scen_meta_list.sort(key=lambda x: (x["year"], x["name"]))
        
        def format_scenario_dropdown(meta_item):
            alt_tag = " [🌌 Альт-история]" if meta_item["is_alt_history"] else ""
            return f"{meta_item['name']}{alt_tag} [Старт: {meta_item['start_date']} | Стран: {meta_item['count']}]"

        sel_meta = st.selectbox("Доступные сценарии (хронологически)", scen_meta_list, format_func=format_scenario_dropdown)
        
        if sel_meta:
            scen_d = sel_meta["data"]
            st.write(f"**Описание:** {scen_d.get('description', '')}")
            st.write(f"**Дата старта:** {scen_d.get('start_date', '')} | **Всего государств в сценарии:** {sel_meta['count']}")
            
            # ЧЕСТНЫЙ ДИСКЛЕЙМЕР
            st.info("⚠️ **Ограничение симуляции:** Даже при наличии подробного лора ИИ-гейммастер может допускать географические или исторические неточности. Для ручной правки используйте Debug/Гейммастер в левой панели.")
            
            st.divider()
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown("#### Уровень сложности (согласие мира с игроком)")
                diff = st.radio("Сложность", ["Шутка", "Лёгкий", "Нормальный", "Хардкор"], index=2, help="Шутка: мир слепо принимает всё; Хардкор: придирается к каждому слову.")
            with col_s2:
                st.markdown("#### Шкала хаоса дипломатии и случайности ботов")
                solar = st.slider("Уровень хаоса поведения стран", 0, 10, 2, help="0: строгий протокол; 5-6: наглость и дерзость; 9-10: безумные ультиматумы капсом и угрозы.")
                
            if st.button("Далее: Выбор державы ➡️", type="primary"):
                st.session_state.selected_scenario = sel_meta["file"]
                st.session_state.selected_diff = diff
                st.session_state.selected_solar = solar
                st.session_state.selected_is_alt = sel_meta["is_alt_history"]
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
        
        st.caption(f"Доступно для выбора: {len(great)} великих держав и {len(minors)} малых государств.")
        sel_country = st.selectbox("Выберите страну", great + ["---"] + minors)
        if sel_country and sel_country != "---":
            c_data = countries[sel_country]
            st.markdown(f"### {sel_country}")
            st.write(f"**Профиль:** {c_data.get('profile', '')}")
            st.write(f"**Регион:** {c_data.get('region', 'Европа')} | **Режим:** {c_data.get('regime', '')} | **Фракция:** {c_data.get('faction', 'Нет')}")
            st.write(f"**Амбиции:** {c_data.get('ambitions', 'Развитие')} | **Страхи:** {c_data.get('fears', 'Кризис')}")
            st.write(f"**Ресурсы:** {c_data.get('resources', 'Информация отсутствует')}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Стабильность", f"{c_data.get('stats', {}).get('stability', 0)}/100")
            c2.metric("Поддержка войны", f"{c_data.get('stats', {}).get('war_support', 0)}/100")
            c3.metric("Боеготовность", f"{c_data.get('stats', {}).get('military_readiness', 0)}/100")
            c4.metric("Оценка армии", c_data.get('stats', {}).get('manpower_approx', 'Неизвестно'))
            
            if st.button("🚀 Начать кампанию", type="primary", use_container_width=True):
                start_new_game_session(
                    st.session_state.target_slot, 
                    st.session_state.selected_scenario, 
                    sel_country, 
                    st.session_state.selected_diff, 
                    st.session_state.selected_solar,
                    st.session_state.selected_is_alt
                )
                st.rerun()