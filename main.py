import streamlit as st
from core.state import apply_pending_rollback, init_session_state, save_game_to_slot
from core.military import ensure_military_loaded
from ui.menu import render_main_menu
from ui.sidebar import render_sidebar
from ui.tabs.tab_news import render_news_tab
from ui.tabs.tab_management import render_management_tab
from ui.tabs.tab_diplomacy import render_diplomacy_tab
from ui.tabs.tab_military import render_military_tab
from ui.tabs.tab_advisors import render_advisors_tab
from ai.pipeline import process_turn_pipeline

st.set_page_config(page_title="Geopolitics AI Engine (Alpha)", layout="wide")

# 1. Безопасное применение отката хода ДО создания любых виджетов
#    (откатывается только игровой мир; заметки и чаты с советниками остаются)
if apply_pending_rollback():
    save_game_to_slot(st.session_state.current_slot)

# 2. Инициализация сессии
init_session_state()

# 3. Ветка А: Главное меню
if not st.session_state.get("in_game", False):
    render_main_menu()
# 4. Ветка Б: Игровой процесс
else:
    # Защита: если держава игрока ликвидирована/распалась -> выбор правопреемника
    _countries = st.session_state.countries
    _me = _countries.get(st.session_state.player_country)
    if _me is None or _me.get("status") == "Спящая":   # ликвидирована или «уснула» после раскола
        st.warning("⚠️ Ваша держава прекратила существование, распалась или была расформирована.")
        st.subheader("🏛 Выберите государство-преемника для продолжения правления:")
        
        avail_countries = [c for c, d in _countries.items() if d.get("status") != "Спящая"] or list(_countries.keys())
        if not avail_countries:
            st.error("На карте мира не осталось суверенных государств.")
            if st.button("Выйти в главное меню"):
                st.session_state.in_game = False
                st.rerun()
        else:
            sel_successor = st.selectbox("Доступные государства на карте:", avail_countries)
            if st.button("👑 Возглавить эту державу", type="primary"):
                st.session_state.player_country = sel_successor
                _countries[sel_successor]["status"] = "Активная"
                ensure_military_loaded(sel_successor)
                st.success(f"Вы приняли бразды правления державой: {sel_successor}")
                st.rerun()
        st.stop()

    # Сайдбар
    render_sidebar()

    # Заголовок
    st.title(f"Ход {st.session_state.turn} | {st.session_state.current_date}")

    # Отчёт о прошлом ходе: сбои агентов, отклонённые данные, замечания ревизора
    _report = st.session_state.get("last_turn_report")
    if _report and _report.get("lines"):
        with st.container(border=True):
            st.markdown(f"**Отчёт о завершённом ходе {_report['turn'] - 1}**")
            for _line in _report["lines"]:
                st.caption(_line)
            if st.button("Скрыть отчёт", key="hide_turn_report"):
                st.session_state.pop("last_turn_report", None)
                st.rerun()

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