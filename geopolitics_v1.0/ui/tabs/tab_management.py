import streamlit as st

def render_management_tab():
    my_c = st.session_state.countries[st.session_state.player_country]
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Стабильность", f"{my_c['stats']['stability']}/100")
    col_m2.metric("Поддержка войны", f"{my_c['stats']['war_support']}/100")
    col_m3.metric("Боеготовность", f"{my_c['stats']['military_readiness']}/100")
    col_m4.metric("Оценка армии", my_c['stats'].get('manpower_approx', 'Неизвестно'))
    
    st.write(f"**Ресурсы:** {my_c.get('resources', 'Стандартное обеспечение')}")
    st.write(f"**Национальные амбиции:** {my_c.get('ambitions', 'Укрепление позиций')}")
    st.write(f"**Главные страхи:** {my_c.get('fears', 'Внутренний раскол')}")
    
    if st.session_state.internal_events:
        st.markdown("### ⚡ Внутренние происшествия")
        for idx_ev, ev in enumerate(st.session_state.internal_events):
            col_ev_t, col_ev_b = st.columns([5, 1])
            with col_ev_t:
                if ev.get("type") == "positive":
                    st.success(f"🟢 **{ev['title']}**\n\n{ev['desc']}\n\n*Эффект:* {ev.get('impact', '')}")
                else:
                    st.error(f"🔴 **{ev['title']}**\n\n{ev['desc']}\n\n*Эффект:* {ev.get('impact', '')}")
            with col_ev_b:
                if st.button("❌ Снять", key=f"dismiss_ev_{idx_ev}", help="Закрыть происшествие"):
                    st.session_state.internal_events.pop(idx_ev)
                    st.rerun()
                
    st.divider()
    st.subheader("📌 Повестка дня и процессы")
    if not my_c.get('current_issues'):
        st.write("Нет активных процессов.")
    else:
        for issue in my_c['current_issues']:
            st.warning(f"**{issue['name']}** | Дедлайн: {issue.get('target_date', 'Бессрочно')} | Статус: *{issue['status']}*")
            
    st.subheader("Приказы на текущий ход")
    st.text_area("Опишите политические, экономические и мобилизационные решения:", key=f"orders_{st.session_state.turn}", height=140)