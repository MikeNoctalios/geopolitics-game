import streamlit as st
from core.state import init_session_state
from ui.menu import render_main_menu
from ui.sidebar import render_sidebar
from ui.tabs.tab_news import render_news_tab
from ui.tabs.tab_management import render_management_tab
from ui.tabs.tab_diplomacy import render_diplomacy_tab
from ui.tabs.tab_military import render_military_tab
from ui.tabs.tab_advisors import render_advisors_tab
from ai.pipeline import process_turn_pipeline

st.set_page_config(page_title="Geopolitics AI Engine (Alpha)", layout="wide")

# 1. Инициализация сессии
init_session_state()

# 2. Ветка А: Главное меню
if not st.session_state.get("in_game", False):
    render_main_menu()
# 3. Ветка Б: Игровой процесс
else:
    # Сайдбар
    render_sidebar()

    # Заголовок
    st.title(f"Ход {st.session_state.turn} | {st.session_state.current_date}")

    # Вкладки
    diplo_badge = f"🤝 Дипломатия ({len(st.session_state.unread_messages)} 📩)" if st.session_state.unread_messages else "🤝 Дипломатия"

    t_news, t_manage, t_diplo, t_mil, t_adv = st.tabs([
        "📰 Сводки и Новости",
        "🏛 Управление",
        diplo_badge,
        "🪖 Армия и ВПК",
        "🧠 Советники"
    ])

    with t_news:
        render_news_tab()
    with t_manage:
        render_management_tab()
    with t_diplo:
        render_diplomacy_tab()
    with t_mil:
        render_military_tab()
    with t_adv:
        render_advisors_tab()

    # Завершение хода
    st.divider()
    warnings = []
    if st.session_state.unread_messages:
        warnings.append(f"Непрочитанные депеши от: {', '.join(st.session_state.unread_messages)}")
    orders_cur = st.session_state.get(f"orders_{st.session_state.turn}", "").strip()
    if not orders_cur:
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
                    process_turn_pipeline(orders_cur)
        else:
            if st.button("⏭ ЗАВЕРШИТЬ ХОД", type="primary", use_container_width=True):
                process_turn_pipeline(orders_cur)