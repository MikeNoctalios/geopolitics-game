import streamlit as st

def normalize_military_category(raw_cat: str) -> str:
    """Приводит любые русские или произвольные категории техники к 4 системным."""
    c = str(raw_cat).lower().strip()
    if any(k in c for k in ["пехот", "винтов", "автомат", "стрелк", "снаряж", "infantry", "small_arms"]):
        return "infantry"
    if any(k in c for k in ["авиа", "самолет", "истребител", "бомбардировщик", "вертолет", "air", "plane"]):
        return "air"
    if any(k in c for k in ["флот", "корабл", "эсминец", "линкор", "подлодк", "катер", "крейсер", "navy", "ship"]):
        return "navy"
    # Все остальное (танки, ОБТ, БМП, артиллерия, ПВО, тягачи) -> ground
    return "ground"

def execute_world_mutations(mutations: dict) -> list:
    """
    Универсальный исполнительный движок мутаций:
    Надежно обрабатывает любые ключи от ИИ и обновляет базу данных игры.
    """
    logs = []
    if not isinstance(mutations, dict):
        return ["Предупреждение: получен некорректный формат мутаций."]

    # 1. Дата
    if mutations.get("set_date"):
        st.session_state.current_date = str(mutations["set_date"])
        logs.append(f"📅 Дата мира: {mutations['set_date']}")

    # 2. Мета-директивы в память мира
    meta_directives = mutations.get("add_ongoing_arcs", [])
    if isinstance(meta_directives, str): meta_directives = [meta_directives]
    if isinstance(meta_directives, list):
        for arc in meta_directives:
            if isinstance(arc, str) and arc:
                st.session_state.ongoing_arcs.append(arc)
                logs.append(f"🧠 Директива для всех агентов: «{arc}»")

    # 3. Мировое событие
    if mutations.get("add_world_event"):
        ev = mutations["add_world_event"]
        if isinstance(ev, dict):
            st.session_state.turn_archives[-1]["world_events"].append({
                "date": st.session_state.current_date,
                "title": ev.get("title", "Исторический сдвиг"),
                "desc": ev.get("desc", "")
            })
            logs.append(f"📰 Событие: {ev.get('title')}")

    # 4. Закрытие происшествий
    if mutations.get("dismiss_internal_event_title"):
        t_del = str(mutations["dismiss_internal_event_title"])
        st.session_state.internal_events = [ev for ev in st.session_state.internal_events if ev.get("title") != t_del]
        logs.append(f"✅ Снято с повестки: {t_del}")

    # 5. Переименование стран
    ren_data = mutations.get("rename_countries", [])
    if isinstance(ren_data, dict):
        ren_data = [{"old_name": k, "new_name": v} for k, v in ren_data.items()]
    elif not isinstance(ren_data, list):
        ren_data = []

    for ren in ren_data:
        if isinstance(ren, dict):
            old_n = ren.get("old_name")
            new_n = ren.get("new_name")
        else: continue
        if old_n in st.session_state.countries and new_n:
            st.session_state.countries[new_n] = st.session_state.countries.pop(old_n)
            if st.session_state.player_country == old_n:
                st.session_state.player_country = new_n
            if st.session_state.get("diplo_target_country") == old_n:
                st.session_state.diplo_target_country = new_n
            for chat_k in list(st.session_state.chats.keys()):
                if old_n in chat_k:
                    new_k = chat_k.replace(old_n, new_n)
                    st.session_state.chats[new_k] = st.session_state.chats.pop(chat_k)
            logs.append(f"🏷️ Держава '{old_n}' переименована в '{new_n}'")

    # 6. Прямая ликвидация стран
    del_data = mutations.get("delete_countries", [])
    if isinstance(del_data, str): del_data = [del_data]
    elif not isinstance(del_data, list): del_data = []
    for del_c in del_data:
        c_name_to_del = del_c if isinstance(del_c, str) else del_c.get("name") if isinstance(del_c, dict) else None
        if c_name_to_del and c_name_to_del in st.session_state.countries:
            del st.session_state.countries[c_name_to_del]
            for chat_k in list(st.session_state.chats.keys()):
                if c_name_to_del in chat_k:
                    del st.session_state.chats[chat_k]
            logs.append(f"❌ Держава '{c_name_to_del}' полностью стерта с лица Земли")

    # 7. Создание новых стран
    spawn_data = mutations.get("spawn_countries", [])
    if isinstance(spawn_data, str): spawn_data = [{"name": spawn_data}]
    elif not isinstance(spawn_data, list): spawn_data = []
    
    for sp in spawn_data:
        if isinstance(sp, str):
            c_name = sp
            sp_dict = {}
        elif isinstance(sp, dict):
            c_name = sp.get("name")
            sp_dict = sp
        else: continue
            
        if c_name:
            st.session_state.countries[c_name] = {
                "status": "Активная",
                "is_great_power": sp_dict.get("is_great_power", False),
                "regime": sp_dict.get("regime", "Республика"),
                "faction": sp_dict.get("faction", "Нет"),
                "region": sp_dict.get("region", "Европа"),
                "ambitions": sp_dict.get("ambitions", "Сохранение суверенитета и порядка."),
                "fears": sp_dict.get("fears", "Внешняя агрессия."),
                "overlord": sp_dict.get("overlord", None),
                "resources": sp_dict.get("resources", "Местные резервы"),
                "stats": sp_dict.get("stats", {
                    "stability": 60, "war_support": 30, 
                    "military_readiness": 40, "manpower_approx": sp_dict.get("manpower_approx", "~100 тыс. чел.")
                }),
                "profile": sp_dict.get("profile", "Суверенное государство."),
                "current_issues": sp_dict.get("current_issues", []),
                "relations": sp_dict.get("relations", {}),
                "military": "genit"
            }
            logs.append(f"🌟 Образовано государство: '{c_name}'")

    # 8. Выдача вооружения (С полной нормализацией любых ключей и категорий)
    add_eq_data = mutations.get("add_equipment", [])
    if isinstance(add_eq_data, dict): add_eq_data = [add_eq_data]
    elif not isinstance(add_eq_data, list): add_eq_data = []
    
    for add_eq in add_eq_data:
        if not isinstance(add_eq, dict): continue
        c_t = add_eq.get("country") or st.session_state.player_country
        if c_t in st.session_state.countries:
            from core.military import ensure_military_loaded
            ensure_military_loaded(c_t)
            
            # Извлечение названия (любые синонимы)
            eq_name = add_eq.get("name") or add_eq.get("model") or add_eq.get("equipment") or add_eq.get("title") or add_eq.get("item") or "Новый образец"
            
            # Извлечение количества (с безопасной конвертацией из строк)
            raw_cnt = add_eq.get("count") or add_eq.get("quantity") or add_eq.get("amount") or add_eq.get("number") or 100
            try:
                eq_count = int(str(raw_cnt).replace(" ", "").replace(",", ""))
            except Exception:
                eq_count = 100
                
            # Нормализация категории в одну из 4 системных
            raw_cat = add_eq.get("category") or add_eq.get("type") or "ground"
            cat = normalize_military_category(raw_cat)
            
            eq_type = add_eq.get("type") or add_eq.get("category") or "Боевая техника"
            eq_specs = add_eq.get("specs") or add_eq.get("description") or "Выдано по распоряжению Гейммастера."
            
            t_mil = st.session_state.countries[c_t].setdefault("military", {})
            if not isinstance(t_mil, dict):
                t_mil = {"infantry": [], "ground": [], "air": [], "navy": []}
                st.session_state.countries[c_t]["military"] = t_mil
                
            t_mil.setdefault(cat, []).append({
                "name": str(eq_name),
                "type": str(eq_type),
                "count": eq_count,
                "production": True,
                "in_service": True,
                "specs": str(eq_specs),
                "evaluation": "Состоит на вооружении.",
                "is_known_globally": True
            })
            logs.append(f"🪖 Для '{c_t}' начислено: {eq_name} ({eq_count:,} ед.) в категорию [{cat}]")

    # 9. Удаление техники
    rem_eq_data = mutations.get("remove_equipment", [])
    if isinstance(rem_eq_data, (str, dict)): rem_eq_data = [rem_eq_data]
    elif not isinstance(rem_eq_data, list): rem_eq_data = []
    for rem_eq in rem_eq_data:
        if isinstance(rem_eq, str): c_t, eq_n = st.session_state.player_country, rem_eq
        elif isinstance(rem_eq, dict): c_t, eq_n = rem_eq.get("country", st.session_state.player_country), rem_eq.get("name")
        else: continue
        if c_t in st.session_state.countries and eq_n:
            t_mil = st.session_state.countries[c_t].get("military", {})
            if isinstance(t_mil, dict):
                for cat_k in ["infantry", "ground", "air", "navy"]:
                    t_mil[cat_k] = [it for it in t_mil.get(cat_k, []) if it.get("name") != eq_n]
                logs.append(f"🗑️ Удален образец '{eq_n}' у державы '{c_t}'")

    # 10. Обновление параметров и статов государств
    upd_dict = mutations.get("update_countries", {})
    if isinstance(upd_dict, dict):
        for upd_c, val in upd_dict.items():
            if upd_c in st.session_state.countries and isinstance(val, dict):
                target = st.session_state.countries[upd_c]
                # Прямое обновление параметров
                for k, v in val.items():
                    if k == "stats" and isinstance(v, dict):
                        target.setdefault("stats", {}).update(v)
                    elif k in ["stability", "war_support", "military_readiness", "manpower_approx"]:
                        target.setdefault("stats", {})[k] = v
                    else:
                        target[k] = v
                logs.append(f"⚙️ Обновлены параметры державы '{upd_c}'")

    return logs