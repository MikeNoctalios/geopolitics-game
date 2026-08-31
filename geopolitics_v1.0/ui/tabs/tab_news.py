import json
import streamlit as st

def render_news_tab():
    for arch in reversed(st.session_state.turn_archives):
        with st.expander(f"📌 Ход {arch['turn']} — {arch['date']}", expanded=(arch['turn'] == st.session_state.turn)):
            col_nw1, col_nw2 = st.columns(2)
            with col_nw1:
                st.markdown("#### 🌍 Мировая арена (События других держав)")
                world_evs = list(reversed(arch.get("world_events", [])))
                if not world_evs:
                    st.caption("В мире сохраняется относительное спокойствие.")
                for we in world_evs:
                    st.info(f"**[{we.get('date', arch['date'])}] {we['title']}**\n\n{we['desc']}")
                
                flavor_evs = list(reversed(arch.get("flavor_events", [])))
                if flavor_evs:
                    with st.expander("🎭 Прочее (Культура, открытия, слухи)", expanded=False):
                        for fe in flavor_evs:
                            st.caption(f"**[{fe.get('date', arch['date'])}] {fe['title']}:** {fe['desc']}")
            
            with col_nw2:
                st.markdown("#### 🏛 О нас (События и реакция на наши указы)")
                player_evs = list(reversed(arch.get("player_events", [])))
                if not player_evs:
                    st.write("Специфических последствий не зафиксировано.")
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