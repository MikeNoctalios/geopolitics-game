import json
import streamlit as st
from ai.client import chat_text, get_ai_client, load_config
from ai.prompts import get_alt_history_directive, get_chaos_persona_instructions
from core.state import get_scenario_world_context

HISTORY_LIMIT = 12   # сколько последних реплик видит министр (раньше — только самый последний вопрос)


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
    chat = st.session_state.advisor_chats[r_k]
    err_key = f"advisor_error_{r_k}"

    with st.container(height=350):
        for a_msg in chat:
            with st.chat_message(a_msg["role"]):
                st.write(a_msg["content"])

    if a_prompt := st.chat_input(f"Спросить ({adv_sel})...", key=f"chat_input_field_{r_k}"):
        chat.append({"role": "user", "content": a_prompt})
        st.session_state.pop(err_key, None)
        st.rerun()

    if chat[-1]["role"] != "user":
        return
    if not cfg.get("api_key"):
        st.warning("Укажите API-ключ в настройках главного меню — без него министр не ответит.")
    elif st.session_state.get(err_key):
        st.error(f"Министр не смог ответить: {st.session_state[err_key]}")
        if st.button("🔁 Повторить запрос", key=f"retry_{r_k}"):
            st.session_state.pop(err_key)
            st.rerun()
    else:
        my_c = st.session_state.countries[st.session_state.player_country]
        stats = my_c.get("stats", {})
        ctx_block = get_alt_history_directive(st.session_state.get("is_alt_history", False),
                                              get_scenario_world_context())
        sys_p = f"""You are the {adv_sel} of {st.session_state.player_country}.
{ctx_block}
{get_chaos_persona_instructions(st.session_state.solar_activity)}
Respond STRICTLY in fluent Russian (1-2 paragraphs).
Date: {st.session_state.current_date}.
Stability: {stats.get('stability')}, War support: {stats.get('war_support')}, Readiness: {stats.get('military_readiness')}.
Active Arcs: {json.dumps(st.session_state.ongoing_arcs, ensure_ascii=False)}."""
        messages = [{"role": "system", "content": sys_p}] + chat[-HISTORY_LIMIT:]
        with st.spinner("Министр готовит ответ..."):
            text, tokens, err = chat_text(get_ai_client(cfg["api_key"], cfg["base_url"]),
                                          cfg["model_name"], messages, temperature=0.7)
        if text:
            chat.append({"role": "assistant", "content": text})
            st.session_state.token_usage["total"] += tokens
        else:
            st.session_state[err_key] = err
        st.rerun()
