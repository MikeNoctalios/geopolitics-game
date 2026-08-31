import json
import streamlit as st
from ai.client import load_config, get_ai_client
from ai.prompts import get_chaos_persona_instructions, get_alt_history_directive
from core.state import get_scenario_world_context

def render_advisors_tab():
    cfg = load_config()
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
    
    with st.container(height=350):
        for a_msg in st.session_state.advisor_chats[r_k]:
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
                world_ctx = get_scenario_world_context()
                ctx_block = get_alt_history_directive(st.session_state.get("is_alt_history", False), world_ctx)
                solar = st.session_state.solar_activity
                chaos_tone = get_chaos_persona_instructions(solar)
                
                sys_p = f"""You are the {adv_sel} of {st.session_state.player_country}.
{ctx_block}
{chaos_tone}
Respond STRICTLY in fluent Russian (1-2 paragraphs).
Current Stability: {my_c['stats'].get('stability')}, Readiness: {my_c['stats'].get('military_readiness')}.
Active Arcs: {json.dumps(st.session_state.ongoing_arcs, ensure_ascii=False)}."""
                r_res = cl.chat.completions.create(model=cfg["model_name"], messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": st.session_state.advisor_chats[r_k][-1]["content"]}], temperature=0.7)
                st.session_state.advisor_chats[r_k].append({"role": "assistant", "content": r_res.choices[0].message.content})
                st.rerun()