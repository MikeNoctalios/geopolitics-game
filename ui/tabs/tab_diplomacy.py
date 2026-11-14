import html
import streamlit as st
from ai.client import load_config, get_ai_client
from ai.agents.conference import (
    agent_simulate_conference_round,
    agent_simulate_conference_voting,
    agent_simulate_conference_walkout,
    agent_conference_foreign_minister_advice
)
from core import world_ops as W


def _esc(text) -> str:
    """Текст от ИИ/игрока попадает в HTML — экранируем, иначе «<» ломает вёрстку."""
    return html.escape(str(text)).replace("\n", "<br>")


def _client(cfg):
    if not cfg.get("api_key"):
        st.warning("Укажите API-ключ в настройках главного меню — без него ИИ-делегаты молчат.")
        return None
    return get_ai_client(cfg["api_key"], cfg["base_url"])


def _book_tokens(tokens):
    st.session_state.token_usage["total"] += tokens


def render_diplomacy_tab():
    cfg = load_config()
    diplo_sub_mode = st.radio(
        "Режим дипломатии",
        ["💬 Двусторонние депеши", "🏛 Международные саммиты и круглый стол"],
        horizontal=True,
        label_visibility="collapsed",
        key="diplo_sub_mode_switch"
    )
    if diplo_sub_mode == "💬 Двусторонние депеши":
        _render_bilateral()
    else:
        _render_summits(cfg)


# =========================================================================
# РЕЖИМ 1: ДВУСТОРОННИЕ ДЕПЕШИ
# =========================================================================
def _render_bilateral():
    me = st.session_state.player_country
    all_targets = [c for c in st.session_state.countries.keys() if c != me]

    def diplo_sort_key(c_name):
        is_unread = 0 if c_name in st.session_state.unread_messages else 1
        is_great = 0 if st.session_state.countries[c_name].get("is_great_power") else 1
        return (is_unread, is_great, c_name)

    sorted_targets = sorted(all_targets, key=diplo_sort_key)
    if not sorted_targets:
        st.info("В мире нет других держав для переписки.")
        return

    def format_diplo_label(c_name):
        c_info = st.session_state.countries.get(c_name, {})
        prefix = ""
        if c_name in st.session_state.unread_messages: prefix += "📩 "
        if c_info.get("is_great_power"): prefix += "⭐ "
        overlord = f" ({c_info['overlord']})" if c_info.get("overlord") else ""
        return f"{prefix}{c_name}{overlord}"

    if st.session_state.get("diplo_target_country") not in sorted_targets:
        st.session_state.diplo_target_country = sorted_targets[0]
    safe_index = sorted_targets.index(st.session_state.diplo_target_country)

    target_c = st.selectbox(
        "Выберите державу для связи:",
        sorted_targets,
        index=safe_index,
        format_func=format_diplo_label,
        key="diplo_country_select_widget"
    )
    st.session_state.diplo_target_country = target_c
    st.session_state.unread_messages.discard(target_c)

    t_data = st.session_state.countries.get(target_c, {})

    with st.expander(f"Досье: {target_c}", expanded=True):
        cd1, cd2 = st.columns(2)
        with cd1:
            st.write(f"**Регион:** {t_data.get('region', 'Европа')}")
            st.write(f"**Режим:** {t_data.get('regime', 'Неизвестно')} | **Фракция:** {t_data.get('faction', 'Нет')}")
            st.write(f"**Отношение к нам:** {(t_data.get('relations') or {}).get(me, 'Нейтральное')}")
        with cd2:
            st.write(f"**Амбиции:** {t_data.get('ambitions', 'Неизвестно')}")
            st.write(f"**Страхи:** {t_data.get('fears', 'Неизвестно')}")
            st.write(f"**Армия (оценка):** {t_data.get('stats', {}).get('manpower_approx', '~500 тыс. чел.')}")

    chat_k = W.chat_key(me, target_c)
    history = st.session_state.chats.setdefault(chat_k, [])

    st.subheader(f"Переписка: {target_c}")
    with st.container(height=380):
        if not history:
            st.caption("История переписки пуста. Отправьте первую депешу.")
        for msg in history:
            if msg["from"] == me:
                st.markdown(f"<div style='text-align: right; color: #4CAF50; padding: 4px;'><b>Вы:</b> {_esc(msg['text'])}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align: left; color: #2196F3; padding: 4px;'><b>{_esc(msg['from'])}:</b> {_esc(msg['text'])}</div>", unsafe_allow_html=True)

    def send_diplo_action():
        msg_t = st.session_state.diplo_msg_input
        if msg_t:
            history.append({"from": me, "text": msg_t})
            st.session_state.pending_diplo.append({"from": me, "to": target_c, "text": msg_t})
            st.session_state.diplo_msg_input = ""

    st.text_area("Текст депеши:", key="diplo_msg_input", height=90)
    st.button("Отправить депешу", on_click=send_diplo_action, type="secondary")
    if st.session_state.pending_diplo:
        st.caption(f"✉️ Депеш ждёт отправки (уйдут с завершением хода): {len(st.session_state.pending_diplo)}")


# =========================================================================
# РЕЖИМ 2: МЕЖДУНАРОДНЫЕ САММИТЫ И КРУГЛЫЙ СТОЛ
# =========================================================================
def _render_summits(cfg):
    conf = st.session_state.active_conference
    if not conf:
        _render_conference_setup()
    else:
        _render_active_conference(cfg, conf)


def _render_conference_setup():
    me = st.session_state.player_country
    st.markdown("### 🏛 Созыв Международного Саммита")
    st.caption("Организуйте многосторонний круглый стол для решения территориальных споров, заключения пактов или урегулирования войн.")

    with st.container(border=True):
        c_title = st.text_input("Название саммита:", value="Мюнхенская мирная конференция", key="conf_init_title")
        c_topic = st.text_area("Повестка дня и первоначальные требования:", value="Урегулирование территориальных споров и подписание пакта о ненападении.", key="conf_init_topic")

        other_nations = [c for c in st.session_state.countries.keys() if c != me]
        c_parts = st.multiselect("Приглашенные державы (Участники):", other_nations, default=other_nations[:3], key="conf_init_parts")

        c_sec = st.radio("Степень секретности переговоров:", ["Все (Публичный саммит)", "Только участники (Секретно)"], horizontal=True, key="conf_init_sec")

        if st.button("📢 Объявить созыв саммита", type="primary", use_container_width=True):
            if c_parts:
                st.session_state.active_conference = W.new_conference(c_title, me, c_parts, c_topic, c_sec)
                st.success("Международный саммит успешно созван!")
                st.rerun()
            else:
                st.error("Необходимо пригласить хотя бы одну державу.")

    # АРХИВ САММИТОВ
    if st.session_state.conference_archives:
        st.divider()
        st.markdown("### 📜 Архив завершенных саммитов и конференций")
        for c_arch in reversed(st.session_state.conference_archives):
            with st.expander(f"🏛 {c_arch['title']} ({c_arch.get('status', 'Завершен')})", expanded=False):
                st.markdown(f"**Повестка дня:** {c_arch['topic']}")
                st.markdown(f"**Участники:** {', '.join(c_arch['participants'])} | **Режим:** {c_arch.get('secrecy', 'Публичный')}")
                if c_arch.get("positions_summary"):
                    st.markdown(f"**Позиции участников и споры:**\n{c_arch['positions_summary']}")
                st.info(f"**Итоговое решение:** {c_arch.get('summary', 'Решение не зафиксировано')}")
                if c_arch.get("minister_debrief"):
                    st.markdown(f"**Аналитическая записка МИД:**\n*{c_arch['minister_debrief']}*")


def _close_conference(conf):
    st.session_state.conference_archives.append(conf)
    st.session_state.active_conference = None


def _speak_round(cfg, conf, player_line, speech, spinner_text):
    """Один круг прений. При сбое ИИ реплика игрока не фиксируется, чтобы её можно было отправить повторно."""
    cl = _client(cfg)
    if not cl:
        return
    with st.spinner(spinner_text):
        res, tokens = agent_simulate_conference_round(
            cl, cfg["model_name"], conf, st.session_state.player_country,
            speech, st.session_state.difficulty, st.session_state.solar_activity)
    _book_tokens(tokens)
    if res.get("_error"):
        st.error(f"Делегаты не ответили (реплика не засчитана): {res['_error']}")
        return
    conf["dialogue"].append({"speaker": st.session_state.player_country, "text": player_line})
    conf["dialogue"].extend(res["statements"])
    st.rerun()


def _walkout(cfg, conf):
    cl = _client(cfg)
    if not cl:
        return
    with st.spinner("Державы реагируют на ваш демарш и завершают саммит без вас..."):
        res_wo, tokens = agent_simulate_conference_walkout(
            cl, cfg["model_name"], conf, st.session_state.player_country,
            st.session_state.difficulty, st.session_state.solar_activity)
    _book_tokens(tokens)
    if res_wo.get("_error"):
        st.error(f"Не удалось смоделировать реакцию, вы остаётесь на саммите: {res_wo['_error']}")
        return
    me = st.session_state.player_country
    conf["status"] = "Сорван демаршем игрока"
    conf["summary"] = f"Демарш державы {me}. {res_wo.get('walkout_reaction_summary', '')} Принято за закрытыми дверями: {res_wo.get('closed_door_resolution', '')}"
    conf["minister_debrief"] = res_wo.get("minister_debrief", "МИД зафиксировал охлаждение отношений.")
    conf["positions_summary"] = "Державы завершили заседание в узком кругу после ухода нашей делегации."
    conf["dialogue"].extend(res_wo["closing_dialogue"])

    W.add_arc(f"Демарш на саммите «{conf['title']}»: {conf['summary']}")
    W.add_world_event(f"Скандал на саммите: {conf['title']}", conf["summary"])
    _close_conference(conf)
    st.warning("Вы покинули переговоры. Итоги внесены в мировую хронику.")
    st.rerun()


def _vote(cfg, conf, final_text, p_vote):
    cl = _client(cfg)
    if not cl:
        return
    me = st.session_state.player_country
    with st.spinner("Счетная комиссия принимает голоса с учетом сложности и позиций..."):
        res_vote, tokens = agent_simulate_conference_voting(
            cl, cfg["model_name"], conf, final_text, me, p_vote,
            st.session_state.difficulty, st.session_state.solar_activity)
    _book_tokens(tokens)
    if res_vote.get("_error"):      # раньше сбой ИИ превращался в «отклонённую» резолюцию
        st.error(f"Голосование не состоялось, попробуйте ещё раз: {res_vote['_error']}")
        return
    conf["votes"] = res_vote["votes"]
    conf["votes"][me] = {"vote": p_vote, "reason": "Голос суверена."}
    conf["passed"] = res_vote["resolution_passed"]
    conf["summary"] = res_vote.get("outcome_summary", "Резолюция рассмотрена.")
    conf["positions_summary"] = res_vote.get("positions_summary", "Позиции участников зафиксированы.")
    conf["minister_debrief"] = res_vote.get("minister_debrief", "МИД зафиксировал итоги голосования.")
    conf["stage"] = "concluded"
    st.rerun()


def _render_active_conference(cfg, conf):
    me = st.session_state.player_country
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown(f"### 🏛 {conf['title']}")
        st.caption(f"Инициатор: **{conf['initiator']}** | Секретность: **{conf['secrecy']}** | Хаос: **{st.session_state.solar_activity}/10**")
    with col_h2:
        # КНОПКА ДЕМАРША / ПОКИНУТЬ ПЕРЕГОВОРЫ
        with st.popover("🚪 Покинуть (Демарш)", use_container_width=True):
            st.error("Вы уверены, что хотите демонстративно покинуть саммит?")
            st.caption("Оставшиеся державы продолжат переговоры за закрытыми дверями без вашего участия.")
            if st.button("Да, совершить демарш", type="primary", key="confirm_walkout_btn"):
                _walkout(cfg, conf)

    st.info(f"📋 **Повестка дня:** {conf['topic']}\n\n👥 **Участники:** {', '.join(conf['participants'])}")

    # СОВЕТНИК МИД ПРЯМО НА САММИТЕ
    with st.expander("🧠 Спросить советника МИД (Конфиденциальный бриф по саммиту)", expanded=False):
        if st.button("Получить оперативный совет МИД", key="ask_fm_summit_btn"):
            cl = _client(cfg)
            if cl:
                with st.spinner("Министр анализирует ход прений за столом..."):
                    advice_text, tokens = agent_conference_foreign_minister_advice(
                        cl, cfg["model_name"], conf, me,
                        st.session_state.difficulty, st.session_state.solar_activity)
                _book_tokens(tokens)
                st.session_state.temp_fm_summit_advice = advice_text
        if st.session_state.get("temp_fm_summit_advice"):
            st.markdown(f"**Доклад Министра:**\n\n{st.session_state.temp_fm_summit_advice}")

    # Стенограмма круглого стола
    st.markdown("#### 📜 Стенограмма круглого стола")
    with st.container(height=320):
        for speech in conf["dialogue"]:
            spk = speech.get("speaker", "Делегат")
            txt = _esc(speech.get("text", ""))
            if spk == me:
                st.markdown(f"<div style='background: #1e3a1e; padding: 8px; border-radius: 5px; margin-bottom: 6px;'><b>{_esc(spk)} (Вы):</b> {txt}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='background: #1e293b; padding: 8px; border-radius: 5px; margin-bottom: 6px;'><b>{_esc(spk)}:</b> {txt}</div>", unsafe_allow_html=True)

    stage = conf["stage"]
    if stage == "discussion":
        _stage_discussion(cfg, conf)
    elif stage == "voting":
        _stage_voting(cfg, conf)
    elif stage == "concluded":
        _stage_concluded(conf)


def _stage_discussion(cfg, conf):
    st.markdown("#### Ваше слово за круглым столом:")
    player_conf_speech = st.text_input("Выступление, требование или компромисс:", key="player_conf_speech_input")

    col_act1, col_act2, col_act3 = st.columns(3)
    with col_act1:
        if st.button("🗣 Взять слово и слушать реакции", use_container_width=True, type="primary"):
            _speak_round(cfg, conf, player_conf_speech or "(Промолчал)", player_conf_speech,
                         "Державы формулируют ответ с учетом хаоса и интересов...")
    with col_act2:
        if st.button("🤫 Воздержаться от комментариев", use_container_width=True):
            _speak_round(cfg, conf, "(Воздержался от комментариев)", None, "Участники продолжают дискуссию...")
    with col_act3:
        if st.button("⚖️ Выдвинуть проект на голосование", use_container_width=True):
            conf["stage"] = "voting"
            st.rerun()


def _stage_voting(cfg, conf):
    st.markdown("### ⚖️ Итоговое голосование по Резолюции")
    final_text = st.text_area("Финальный текст проекта резолюции / договора:", value=conf.get("final_proposal") or conf["topic"], key="final_res_text")
    conf["final_proposal"] = final_text

    col_v1, col_v2, col_v3 = st.columns(3)
    p_vote = None
    with col_v1:
        if st.button("✅ Голосовать «ЗА»", use_container_width=True, type="primary"):
            p_vote = "За"
    with col_v2:
        if st.button("❌ Голосовать «ПРОТИВ»", use_container_width=True):
            p_vote = "Против"
    with col_v3:
        if st.button("⚪ «ВОЗДЕРЖАТЬСЯ»", use_container_width=True):
            p_vote = "Воздержался"
    if p_vote:
        _vote(cfg, conf, final_text, p_vote)


def _stage_concluded(conf):
    st.markdown("### 🏆 Итоги голосования и Резолюция")
    if conf.get("passed"):
        st.success(f"🎉 **РЕЗОЛЮЦИЯ ПРИНЯТА БОЛЬШИНСТВОМ ГОЛОСОВ!**\n\n{conf.get('summary')}")
    else:
        st.error(f"❌ **РЕЗОЛЮЦИЯ ОТКЛОНЕНА.**\n\n{conf.get('summary')}")

    st.markdown("#### Поименные голоса участников:")
    for c_v, v_data in conf.get("votes", {}).items():
        v_type = v_data.get("vote", "Воздержался")
        v_clr = "🟢" if v_type == "За" else "🔴" if v_type == "Против" else "⚪"
        st.write(f"{v_clr} **{c_v}:** {v_type} — *{v_data.get('reason', '')}*")

    if st.button("📜 Утвердить итоги и закрыть саммит", type="primary", use_container_width=True):
        conf["status"] = "Принята" if conf.get("passed") else "Отклонена"
        if conf.get("passed"):
            W.add_arc(f"Итоги саммита «{conf['title']}»: {conf.get('summary')}")
            W.add_world_event(f"Итоги саммита: {conf['title']}", f"Принята резолюция: {conf.get('summary')}")
        _close_conference(conf)
        st.success("Саммит завершен, дипломатические решения вступили в силу!")
        st.rerun()
