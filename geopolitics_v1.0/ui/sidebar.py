import streamlit as st
from ai.client import load_config, get_ai_client
from ai.agents.gm import agent_gm_orchestrator
from core.state import save_game_to_slot
from core.commands import execute_command_pipeline
from ui.exports import generate_raw_game_log_txt, generate_newspaper_html

def render_sidebar():
    cfg = load_config()
    
    def prev_note_page():
        if st.session_state.note_page_num > 1:
            st.session_state.note_page_num -= 1

    def next_note_page():
        if st.session_state.note_page_num < 99:
            st.session_state.note_page_num += 1

    with st.sidebar:
        st.markdown(f"### 🏛 {st.session_state.player_country}")
        alt_label = " | 🌌 Альт-история" if st.session_state.get("is_alt_history") else ""
        st.caption(f"Сложность: {st.session_state.difficulty} | Хаос: {st.session_state.solar_activity}/10{alt_label}")
        st.markdown(f"**Ход {st.session_state.turn} | {st.session_state.current_date}**")
        if st.session_state.alarm_clock_active:
            st.caption("🔔 Режим «Будильник»: ВКЛ")
        
        if st.button("💾 Сохранить и выйти в меню", use_container_width=True):
            save_game_to_slot(st.session_state.current_slot)
            st.session_state.in_game = False
            st.rerun()
            
        st.divider()
        
        # Блокнот
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
            
        # Дебаг и Гейммастер
        with st.expander("🛠 Debug, Гейммастер и Будильник", expanded=False):
            st.markdown(f"**Расход токенов:** За ход: ~{st.session_state.token_usage['turn']} | Всего: ~{st.session_state.token_usage['total']}")
            st.session_state.autosave_interval = st.number_input("Автосохранение каждые (ходов):", min_value=1, max_value=10, value=st.session_state.autosave_interval)
            
            # Будильник
            st.divider()
            if not st.session_state.alarm_clock_active:
                with st.popover("⏰ Включить «Будильник» (Пробуждение мира)", use_container_width=True):
                    st.warning("Режим активирует все страны и утраивает поток мировых новостей (4 макрорегиона за ход).")
                    if st.button("🚀 Разбудить все страны"):
                        st.session_state.alarm_clock_active = True
                        for c_k in st.session_state.countries:
                            st.session_state.countries[c_k]["status"] = "Активная"
                        st.success("Все страны мира пробуждены!")
                        st.rerun()
            else:
                if st.button("🔕 Отключить «Будильник»", use_container_width=True):
                    st.session_state.alarm_clock_active = False
                    st.info("Режим будильника деактивирован.")
                    st.rerun()

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
            st.download_button("📥 Скачать полный лог (.txt)", data=raw_log_txt, file_name=f"full_log_{st.session_state.player_country}_turn{st.session_state.turn}.txt", mime="text/plain", use_container_width=True)
            
            newspaper_html = generate_newspaper_html()
            st.download_button("🗞️ Скачать газетную хронику (.html)", data=newspaper_html, file_name=f"gazette_{st.session_state.player_country}_turn{st.session_state.turn}.html", mime="text/html", use_container_width=True)

            st.divider()
            st.markdown("#### 🤖 Мета-Гейммастер (Реестр команд)")
            with st.container(height=380):
                if not st.session_state.gm_chat:
                    st.caption("Гейммастер готов исполнить системные команды...")
                for g_msg in st.session_state.gm_chat[-20:]:
                    with st.chat_message(g_msg["role"]):
                        st.write(g_msg["content"])
                    
            if gm_input := st.chat_input("Указание Гейммастеру...", key="gm_direct_chat_input"):
                if cfg.get("api_key"):
                    cl = get_ai_client(cfg["api_key"], cfg["base_url"])
                    with st.spinner("Диспетчер команд обрабатывает директиву..."):
                        try:
                            gm_res, t_count = agent_gm_orchestrator(cl, cfg["model_name"], gm_input, {
                                "player_country": st.session_state.player_country,
                                "countries": st.session_state.countries,
                                "current_date": st.session_state.current_date,
                                "turn": st.session_state.turn,
                                "is_alt_history": st.session_state.get("is_alt_history", False)
                            })
                            st.session_state.token_usage["total"] += t_count
                            st.session_state.gm_chat.append({"role": "user", "content": gm_input})
                            st.session_state.gm_chat.append({"role": "assistant", "content": gm_res.get("confirmation_message", "Команды приведены в исполнение.")})
                            
                            # Исполнение через атомарный Диспетчер Команд
                            command_logs = execute_command_pipeline(gm_res.get("commands", []))
                            for c_log in command_logs:
                                st.session_state.gm_chat.append({"role": "assistant", "content": c_log})
                        except Exception as e:
                            st.session_state.gm_chat.append({"role": "assistant", "content": f"Ошибка исполнения: {e}"})
                        st.rerun()