import streamlit as st
from core.military import ensure_military_loaded, audit_military_catalog, make_rd_project, LANDLOCKED_NATIONS
from core.world_ops import to_int
from ai.client import load_config, get_ai_client

def render_military_tab():
    ensure_military_loaded(st.session_state.player_country)
    my_c = st.session_state.countries[st.session_state.player_country]
    my_mil = my_c.get("military", {})
    if not isinstance(my_mil, dict):
        my_mil = {"infantry": [], "ground": [], "air": [], "navy": []}
        my_c["military"] = my_mil

    total_items_count = sum(len(v) for v in my_mil.values() if isinstance(v, list))

    col_mil_top1, col_mil_top2 = st.columns([3, 1])
    with col_mil_top1:
        mil_category = st.radio(
            "Подраздел ВПК",
            [
                "🪖 Пехота",
                "🚜 Бронетехника/Арт",
                "✈️ Авиация",
                "⚓ Флот",
                "📦 Консервация",
                "🎯 Полигон и КБ",
                "🔍 Разведка"
            ],
            horizontal=True,
            label_visibility="collapsed",
            key="mil_category_nav_7"
        )
    with col_mil_top2:
        if mil_category not in ["🔍 Разведка", "🎯 Полигон и КБ"]:
            if st.button("🔄 Аудит реестра ВПК", help="Генеральный инспектор наведёт порядок, пересчитает технику и исправит ошибки"):
                cfg_l = load_config()
                if not cfg_l.get("api_key"):
                    st.warning("Укажите API-ключ в настройках главного меню.")
                else:
                    cl = get_ai_client(cfg_l["api_key"], cfg_l["base_url"])
                    with st.spinner("Инспекция ВПК проводит аудит вооружения..."):
                        audited, err = audit_military_catalog(
                            cl, cfg_l["model_name"], st.session_state.player_country,
                            my_mil, st.session_state.current_date, my_c['stats'].get('manpower_approx', '~100 тыс. чел.')
                        )
                    if err:
                        st.error(f"Аудит не удался, реестр не изменён: {err}")
                    else:
                        st.session_state.countries[st.session_state.player_country]["military"] = audited
                        st.success("Реестр ВПК успешно пересчитан и реорганизован!")
                        st.rerun()

    if total_items_count > 18 and mil_category not in ["🔍 Разведка", "🎯 Полигон и КБ"]:
        st.warning(f"⚠️ Парк техники перегружен ({total_items_count} позиций). Рекомендуется списать устаревшую технику или провести аудит.")

    cat_map = {
        "🪖 Пехота": "infantry",
        "🚜 Бронетехника/Арт": "ground",
        "✈️ Авиация": "air",
        "⚓ Флот": "navy"
    }

    if mil_category in cat_map:
        c_key = cat_map[mil_category]
        if c_key == "infantry":
            st.info(f"📊 Численность действующей армии: **{my_c['stats'].get('manpower_approx', 'Неизвестно')}**")

        active_items = [it for it in my_mil.get(c_key, []) if it.get("in_service", True)]

        if not active_items:
            if c_key == "navy":
                st.warning("⚓ Военно-морской флот отсутствует (держава не имеет флота или выхода к морю).")
            elif c_key == "air":
                st.info("✈️ Военная авиация отсутствует на вооружении данной державы.")
            elif c_key == "ground":
                st.info("🚜 Тяжелая бронетехника отсутствует на вооружении.")
            else:
                st.write("На вооружении нет единиц данной категории.")
        else:
            for j, eq in enumerate(active_items):
                prod_str = "В производстве" if eq.get("production") else "Производство остановлено"

                with st.expander(f"{eq.get('name', 'Образец')} — {eq.get('count', 0):,} ед. [{prod_str}]", expanded=True):
                    st.write(f"**Тип:** {eq.get('type', '')}")
                    st.write(f"**ТТХ:** {eq.get('specs', '')}")
                    st.write(f"**Оценка военных:** *{eq.get('evaluation', '')}*")

                    c_b1, c_b2, c_b3, c_b4 = st.columns(4)
                    with c_b1:
                        if eq.get("production"):
                            if st.button("Снять с производства", key=f"act_stop_{c_key}_{j}"):
                                eq["production"] = False
                                st.rerun()
                        else:
                            if st.button("Возобновить выпуск", key=f"act_start_{c_key}_{j}"):
                                eq["production"] = True
                                st.rerun()
                    with c_b2:
                        with st.popover("📦 На консервацию"):
                            st.warning("Снять образец с вооружения и отправить в резерв? Производство будет остановлено.")
                            if st.button("Подтвердить консервацию", key=f"act_moth_{c_key}_{j}"):
                                eq["in_service"] = False
                                eq["production"] = False
                                st.rerun()
                    with c_b3:
                        with st.popover("✏️ Имя"):
                            new_custom_name = st.text_input("Новое название:", value=eq.get("name", ""), key=f"rename_in_{c_key}_{j}")
                            if st.button("Сохранить", key=f"save_rename_{c_key}_{j}"):
                                eq["name"] = new_custom_name
                                st.rerun()
                    with c_b4:
                        in_rd = any(p.get("base_equipment", "") == eq.get("name", "") for p in st.session_state.rd_projects)
                        if in_rd:
                            st.info("🎯 КБ ведет разработку")
                        else:
                            if st.button("Запросить модернизацию", key=f"act_mod_{c_key}_{j}"):
                                time_map = {"infantry": "9 Месяцев", "ground": "1.5 Года", "air": "2 Года", "navy": "3 Года"}
                                st.session_state.rd_projects.append(make_rd_project(
                                    f"Модификация {eq.get('name', 'Оружия')}", eq.get("name", "Платформа"), c_key,
                                    eq.get("type", ""), time_map.get(c_key, "1 Год"), 15, "Проектирование чертежей",
                                    f"Улучшенный вариант платформы {eq.get('name', '')}"))
                                st.success(f"Заявка передана в КБ. Срок НИОКР: {time_map.get(c_key, '1 Год')}.")
                                st.rerun()

    elif mil_category == "📦 Консервация":
        st.markdown("#### 📦 Склад резерва и консервации")
        mothballed = []
        for cat_k, items in my_mil.items():
            for idx_it, eq in enumerate(items):
                if not eq.get("in_service", True):
                    mothballed.append((cat_k, idx_it, eq))

        if not mothballed:
            st.info("Склады консервации пусты. Вся техника находится на действительной службе.")
        else:
            for cat_k, idx_it, eq in mothballed:
                with st.expander(f"📦 {eq.get('name', 'Образец')} ({eq.get('type', '')}) — {eq.get('count', 0):,} ед. [НА КОНСЕРВАЦИИ]", expanded=True):
                    st.write(f"**ТТХ:** {eq.get('specs', '')}")
                    st.write(f"**Состояние:** *{eq.get('evaluation', '')}*")

                    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                    with col_m1:
                        if st.button("🔙 В строй", key=f"unmoth_{cat_k}_{idx_it}"):
                            eq["in_service"] = True
                            st.success(f"{eq.get('name')} возвращен в действующую армию!")
                            st.rerun()
                    with col_m2:
                        with st.popover("✏️ Имя"):
                            new_custom_name = st.text_input("Новое название:", value=eq.get("name", ""), key=f"rename_moth_{cat_k}_{idx_it}")
                            if st.button("Сохранить", key=f"save_moth_rename_{cat_k}_{idx_it}"):
                                eq["name"] = new_custom_name
                                st.rerun()
                    with col_m3:
                        if st.button("🎯 Модернизация", key=f"moth_mod_{cat_k}_{idx_it}"):
                            time_map = {"infantry": "9 Месяцев", "ground": "1.5 Года", "air": "2 Года", "navy": "3 Года"}
                            st.session_state.rd_projects.append(make_rd_project(
                                f"Глубокая модернизация {eq.get('name', '')}", eq.get("name", "Платформа"), cat_k,
                                eq.get("type", ""), time_map.get(cat_k, "1 Год"), 20, "Разборка образца и замена узлов",
                                f"Капитальная модернизация со складов консервации: {eq.get('name')}",
                                "Проводятся испытания узлов на износ."))
                            st.success("Образец передан на полигон КБ!")
                            st.rerun()
                    with col_m4:
                        if st.button("❌ В утиль", key=f"scrap_{cat_k}_{idx_it}", help="Навсегда разобрать на металл"):
                            my_mil[cat_k].pop(idx_it)
                            st.rerun()

    elif mil_category == "🎯 Полигон и КБ":
        st.markdown("#### 🎯 Полигон испытаний и Конструкторские Бюро (НИОКР)")
        if not st.session_state.rd_projects:
            st.info("В данный момент КБ не ведут активных разработок. Вы можете запросить модернизацию любого образца во вкладке вооружения.")
        else:
            for idx_p, proj in enumerate(st.session_state.rd_projects):
                with st.container(border=True):
                    st.markdown(f"### 🔬 Проект: {proj.get('name', 'Новый образец')}")
                    st.write(f"**Базовая платформа:** {proj.get('base_equipment', 'Новая разработка')} | **Срок НИОКР:** {proj.get('target_date', '1 Год')}")
                    prog = max(0, min(100, to_int(proj.get("progress", 10), 10)))
                    st.progress(prog / 100, text=f"Прогресс разработки: {prog}% [{proj.get('status', 'Испытания')}]")
                    st.write(f"**Планируемые ТТХ:** {proj.get('specs', '')}")
                    st.info(f"📋 **Сводка с полигона:** {proj.get('polygon_report', 'Проводятся замеры узлов.')}")

                    if proj.get("ready_for_tender") or prog >= 100:
                        st.success("🏆 **Госиспытания завершены! Прототип готов к принятию на вооружение.**")
                        col_p_in, col_p_act1, col_p_act2, col_p_act3 = st.columns([2, 1, 1, 1])
                        with col_p_in:
                            adopt_name = st.text_input("Армейское обозначение:", value=proj.get("name", ""), key=f"adopt_name_{idx_p}")
                        with col_p_act1:
                            if st.button("✅ Принять в серию", key=f"acc_rd_{idx_p}", type="primary"):
                                c_target = proj.get("category", "ground")
                                my_mil.setdefault(c_target, []).append({
                                    "name": adopt_name if adopt_name else proj.get("name", "Новый образец"),
                                    "type": proj.get("type", "Модернизированный"),
                                    "count": 100,
                                    "production": True,
                                    "in_service": True,
                                    "specs": proj.get("specs", ""),
                                    "evaluation": proj.get("polygon_report", "Принят по результатам полигонных испытаний."),
                                    "is_known_globally": False
                                })
                                st.session_state.rd_projects.pop(idx_p)
                                st.success(f"{adopt_name} запущен в серийное производство!")
                                st.rerun()
                        with col_p_act2:
                            if st.button("🛠 Доработка (+6 мес.)", key=f"refine_rd_{idx_p}"):
                                proj["progress"] = 75
                                proj["ready_for_tender"] = False
                                proj["status"] = "Устранение полигонных замечаний"
                                st.rerun()
                        with col_p_act3:
                            if st.button("❌ Закрыть проект", key=f"cancel_rd_{idx_p}"):
                                st.session_state.rd_projects.pop(idx_p)
                                st.rerun()

    elif mil_category == "🔍 Разведка":
        st.markdown("#### 🕵️ Разведданные Генерального штаба")
        intel_targets = [c for c in st.session_state.countries.keys() if c != st.session_state.player_country]
        if not intel_targets:
            st.info("Нет других держав для разведки.")
            return
        other_c = st.selectbox("Выберите державу для изучения разведки:", intel_targets)
        ensure_military_loaded(other_c)
        other_c_data = st.session_state.countries[other_c]
        other_mil = other_c_data.get("military", {})

        col_rev_top1, col_rev_top2 = st.columns([3, 1])
        with col_rev_top1:
            st.metric(f"Оценочная численность армии ({other_c})", other_c_data.get("stats", {}).get("manpower_approx", "~500 тыс. чел."))
        with col_rev_top2:
            if st.button("🔄 Аудит чужого ВПК", help="Пересчитать и упорядочить вооружение этой страны с помощью ИИ"):
                cfg_l = load_config()
                if not cfg_l.get("api_key"):
                    st.warning("Укажите API-ключ в настройках главного меню.")
                else:
                    cl = get_ai_client(cfg_l["api_key"], cfg_l["base_url"])
                    with st.spinner(f"Анализ ВПК ({other_c})..."):
                        audited, err = audit_military_catalog(
                            cl, cfg_l["model_name"], other_c,
                            other_mil, st.session_state.current_date, other_c_data.get("stats", {}).get("manpower_approx", "~100 тыс. чел.")
                        )
                    if err:
                        st.error(f"Аудит не удался: {err}")
                    else:
                        other_c_data["military"] = audited
                        st.success("Данные разведки упорядочены!")
                        st.rerun()

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("##### 🪖 Стрелковое вооружение")
            known_inf = [it for it in other_mil.get("infantry", []) if it.get("is_known_globally")]
            if known_inf:
                for kit in known_inf: st.write(f"• **{kit.get('name')}** (~{kit.get('count', '?')} ед.)")
            else: st.caption("Конкретные образцы засекречены или отсутствуют.")

            st.markdown("##### 🚜 Бронетехника и артиллерия")
            known_gr = [it for it in other_mil.get("ground", []) if it.get("is_known_globally")]
            if known_gr:
                for kit in known_gr: st.write(f"• **{kit.get('name')}** ({kit.get('type', '')}) — ~{kit.get('count', '?')} ед.")
            else: st.caption("Тяжелая техника отсутствует или засекречена.")

        with col_r2:
            st.markdown("##### ✈️ Военная авиация")
            known_air = [it for it in other_mil.get("air", []) if it.get("is_known_globally")]
            if known_air:
                for kit in known_air: st.write(f"• **{kit.get('name')}** ({kit.get('type', '')}) — ~{kit.get('count', '?')} ед.")
            else: st.caption("Военная авиация отсутствует или засекречена.")

            st.markdown("##### ⚓ Военно-морской флот")
            known_navy = [it for it in other_mil.get("navy", []) if it.get("is_known_globally")]
            if known_navy:
                for kit in known_navy: st.write(f"• **{kit.get('name')}** ({kit.get('type', '')}) — {kit.get('count', '?')} ед.")
            else:
                if other_c in LANDLOCKED_NATIONS:
                    st.caption("⚓ Держава не имеет выхода к морю.")
                else:
                    st.caption("Флот отсутствует или скрыт туманом войны.")
