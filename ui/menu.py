import os
import json
import streamlit as st
from ai.client import load_config, save_config, test_connection
from core.state import SCENARIOS_DIR, get_slot_path, get_slot_info, load_game_from_slot, delete_slot, validate_save
from core.time_system import extract_year
from core.game import start_new_game_session

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
            if st.button("🔌 Проверить подключение"):
                with st.spinner("Пробный запрос к модели..."):
                    ok, msg = test_connection(load_config())
                (st.success if ok else st.error)(msg)

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
                        try:
                            load_game_from_slot(i)
                            st.rerun()
                        except (ValueError, OSError) as e:
                            st.error(f"Сохранение не загрузилось: {e}")

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
                            problem = validate_save(data)
                            if problem:
                                st.error(f"Файл не подходит: {problem}")
                            else:
                                with open(get_slot_path(i), "w", encoding="utf-8") as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                st.success("Сохранение загружено!")
                                st.rerun()
                        except ValueError as e:
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
                try:
                    start_new_game_session(
                        st.session_state.target_slot,
                        st.session_state.selected_scenario,
                        sel_country,
                        st.session_state.selected_diff,
                        st.session_state.selected_solar,
                        st.session_state.selected_is_alt
                    )
                except (ValueError, OSError, KeyError) as e:
                    st.error(f"Не удалось начать кампанию: {e}")
                else:
                    st.rerun()
