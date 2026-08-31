import streamlit as st
from core.military import ensure_military_loaded, normalize_military_category

COMMAND_CATALOG_DOCS = """
CATALOG OF EXECUTABLE SYSTEM COMMANDS:

1. GEO_STATE:
   - DELETE_COUNTRY {"country": "<Name>"}
   - SPAWN_COUNTRY {"name": "<Name>", "region": "Европа"|"Азия"|"Америка"|"Ближний Восток", "regime": "<Regime>", "manpower": "<e.g. ~1 млн. чел.>"}
   - RENAME_COUNTRY {"old_name": "<Old>", "new_name": "<New>"}
   - SET_DATE {"date": "<e.g. 15 Мая 1941>"}

2. MILITARY_VPK:
   - GRANT_EQUIPMENT {"country": "<Nation>", "name": "<Model>", "count": <int>, "category": "ground"|"infantry"|"air"|"navy", "type": "<Type>", "specs": "<Specs>"}
   - REMOVE_EQUIPMENT {"country": "<Nation>", "name": "<Model>"}
   - RENAME_EQUIPMENT {"country": "<Nation>", "old_name": "<Old>", "new_name": "<New>"}
   - ADD_RD_TEST {"country": "<Nation>", "name": "<Prototype Name>", "category": "ground"|"infantry"|"air"|"navy", "duration": "<e.g. 2 Дня or 1.5 Года>", "specs": "<Specs>", "status": "<Status>"}
   - COMPLETE_RD_TEST {"project_name": "<Name>"}

3. DOMESTIC:
   - SET_STATS {"country": "<Nation>", "stability": <int 0-100>, "war_support": <int 0-100>, "military_readiness": <int 0-100>}
   - SET_REGIME {"country": "<Nation>", "regime": "<Regime>", "faction": "<Faction>"}
   - SET_RESOURCES {"country": "<Nation>", "resources": "<e.g. Нефть: избыток, Уран: залежи>"}
   - TRIGGER_INTERNAL_EVENT {"title": "<Title>", "desc": "<Desc>", "type": "positive"|"negative", "impact": "<Impact>"}

4. NARRATIVE_NEWS & CONFERENCES:
   - PUBLISH_WORLD_NEWS {"title": "<Headline>", "desc": "<News Body>"}
   - SET_LORE_DIRECTIVE {"directive": "<Historical fact for all agents to remember>"}
   - START_CONFERENCE {"title": "<Title>", "initiator": "<Nation>", "participants": ["<Country 1>", "<Country 2>"], "topic": "<Agenda>", "secrecy": "Все"|"Только участники"}
"""

def execute_single_command(cmd_name: str, params: dict) -> str:
    cmd = str(cmd_name).upper().strip()
    p = params if isinstance(params, dict) else {}
    
    # ----------------------------------------------------
    # 1. GEO_STATE
    # ----------------------------------------------------
    if cmd == "DELETE_COUNTRY":
        c_del = p.get("country")
        if c_del and c_del in st.session_state.countries:
            del st.session_state.countries[c_del]
            for chat_k in list(st.session_state.chats.keys()):
                if c_del in chat_k: del st.session_state.chats[chat_k]
            return f"❌ [Карта] Держава '{c_del}' ликвидирована и удалена из мира"
            
    elif cmd == "SPAWN_COUNTRY":
        c_name = p.get("name")
        if c_name:
            st.session_state.countries[c_name] = {
                "status": "Активная",
                "is_great_power": p.get("is_great_power", False),
                "regime": p.get("regime", "Республика"),
                "faction": p.get("faction", "Нет"),
                "region": p.get("region", "Европа"),
                "ambitions": p.get("ambitions", "Суверенитет и развитие."),
                "fears": p.get("fears", "Внешняя агрессия."),
                "overlord": p.get("overlord", None),
                "resources": p.get("resources", "Местные резервы"),
                "stats": {
                    "stability": int(p.get("stability", 60)),
                    "war_support": int(p.get("war_support", 30)),
                    "military_readiness": int(p.get("military_readiness", 40)),
                    "manpower_approx": str(p.get("manpower", "~100 тыс. чел."))
                },
                "profile": str(p.get("profile", "Суверенное государство.")),
                "current_issues": [],
                "relations": {},
                "military": "genit"
            }
            return f"🌟 [Карта] Образовано новое государство: '{c_name}'"

    elif cmd == "RENAME_COUNTRY":
        old_n, new_n = p.get("old_name"), p.get("new_name")
        if old_n in st.session_state.countries and new_n:
            st.session_state.countries[new_n] = st.session_state.countries.pop(old_n)
            if st.session_state.player_country == old_n:
                st.session_state.player_country = new_n
            if st.session_state.get("diplo_target_country") == old_n:
                st.session_state.diplo_target_country = new_n
            for chat_k in list(st.session_state.chats.keys()):
                if old_n in chat_k:
                    st.session_state.chats[chat_k.replace(old_n, new_n)] = st.session_state.chats.pop(chat_k)
            return f"🏷️ [Карта] Держава '{old_n}' переименована в '{new_n}'"

    elif cmd == "SET_DATE":
        new_d = p.get("date")
        if new_d:
            st.session_state.current_date = str(new_d)
            return f"📅 [Календарь] Дата мира установлена на: {new_d}"

    # ----------------------------------------------------
    # 2. MILITARY_VPK
    # ----------------------------------------------------
    elif cmd == "GRANT_EQUIPMENT":
        c_t = p.get("country") or st.session_state.player_country
        if c_t in st.session_state.countries:
            ensure_military_loaded(c_t)
            eq_name = p.get("name", "Новый образец")
            raw_cnt = p.get("count", 100)
            try: eq_count = int(str(raw_cnt).replace(" ", "").replace(",", ""))
            except Exception: eq_count = 100
            
            cat = normalize_military_category(p.get("category", "ground"))
            eq_type = p.get("type", "Боевое оснащение")
            eq_specs = p.get("specs", "Выдано по правительственному акту.")
            
            t_mil = st.session_state.countries[c_t].setdefault("military", {})
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
            return f"🪖 [ВПК] Для '{c_t}' начислено: {eq_name} ({eq_count:,} ед.) [{cat}]"

    elif cmd == "ADD_RD_TEST":
        c_t = p.get("country") or st.session_state.player_country
        p_name = p.get("name", "Перспективный образец")
        cat = normalize_military_category(p.get("category", "navy"))
        dur = p.get("duration", "1 Год")
        specs = p.get("specs", "Проект на полигоне КБ.")
        status = p.get("status", "Полигонные испытания")
        
        st.session_state.rd_projects.append({
            "id": f"proj_cmd_{len(st.session_state.rd_projects)+1}",
            "name": str(p_name),
            "base_equipment": str(p_name),
            "category": cat,
            "type": p.get("type", "Опытный прототип"),
            "start_date": st.session_state.current_date,
            "target_date": str(dur),
            "progress": int(p.get("progress", 15)),
            "status": str(status),
            "specs": str(specs),
            "polygon_report": "Проводятся замеры гидродинамики и полигонные тесты узлов.",
            "ready_for_tender": False
        })
        return f"🎯 [Полигон КБ] Запущен проект испытаний: '{p_name}' [{cat}] (Срок: {dur})"

    elif cmd == "COMPLETE_RD_TEST":
        proj_n = p.get("project_name")
        for proj in st.session_state.rd_projects:
            if proj_n in proj.get("name", ""):
                proj["progress"] = 100
                proj["ready_for_tender"] = True
                proj["status"] = "Госиспытания успешно завершены"
                return f"🏆 [Полигон КБ] Проект '{proj['name']}' досрочно завершил испытания и готов к принятию!"

    elif cmd == "REMOVE_EQUIPMENT":
        c_t = p.get("country") or st.session_state.player_country
        eq_n = p.get("name")
        if c_t in st.session_state.countries and eq_n:
            t_mil = st.session_state.countries[c_t].get("military", {})
            if isinstance(t_mil, dict):
                for cat_k in ["infantry", "ground", "air", "navy"]:
                    t_mil[cat_k] = [it for it in t_mil.get(cat_k, []) if it.get("name") != eq_n]
                return f"🗑️ [ВПК] Образец '{eq_n}' списан из арсенала '{c_t}'"

    # ----------------------------------------------------
    # 3. DOMESTIC
    # ----------------------------------------------------
    elif cmd == "SET_STATS":
        c_t = p.get("country") or st.session_state.player_country
        if c_t in st.session_state.countries:
            t_stats = st.session_state.countries[c_t].setdefault("stats", {})
            for k in ["stability", "war_support", "military_readiness"]:
                if k in p and p[k] is not None:
                    t_stats[k] = int(p[k])
            if "manpower" in p: t_stats["manpower_approx"] = str(p["manpower"])
            return f"⚙️ [Параметры] Обновлены показатели державы '{c_t}'"

    elif cmd == "SET_REGIME":
        c_t = p.get("country") or st.session_state.player_country
        if c_t in st.session_state.countries:
            if "regime" in p: st.session_state.countries[c_t]["regime"] = str(p["regime"])
            if "faction" in p: st.session_state.countries[c_t]["faction"] = str(p["faction"])
            return f"👑 [Власть] Для '{c_t}' установлен режим: {p.get('regime')}"

    elif cmd == "SET_RESOURCES":
        c_t = p.get("country") or st.session_state.player_country
        if c_t in st.session_state.countries:
            st.session_state.countries[c_t]["resources"] = str(p.get("resources", ""))
            return f"📦 [Ресурсы] Обновлена ресурсная база державы '{c_t}'"

    elif cmd == "TRIGGER_INTERNAL_EVENT":
        st.session_state.internal_events.append({
            "title": str(p.get("title", "Внутреннее событие")),
            "desc": str(p.get("desc", "")),
            "type": str(p.get("type", "positive")),
            "impact": str(p.get("impact", ""))
        })
        return f"⚡ [Кабинет] Внутреннее происшествие: {p.get('title')}"

    # ----------------------------------------------------
    # 4. NARRATIVE_NEWS & CONFERENCES
    # ----------------------------------------------------
    elif cmd == "PUBLISH_WORLD_NEWS":
        t_n, d_n = p.get("title", "Мировая сенсация"), p.get("desc", "")
        st.session_state.turn_archives[-1]["world_events"].append({
            "date": st.session_state.current_date,
            "title": str(t_n),
            "desc": str(d_n)
        })
        return f"📰 [Мировые Новости] Опубликована статья: «{t_n}»"

    elif cmd == "SET_LORE_DIRECTIVE":
        direct = p.get("directive")
        if direct:
            st.session_state.ongoing_arcs.append(str(direct))
            return None # Тихое внедрение

    elif cmd == "START_CONFERENCE":
        title = p.get("title", "Международный саммит")
        initiator = p.get("initiator", st.session_state.player_country)
        parts = p.get("participants", [st.session_state.player_country])
        if initiator not in parts: parts.append(initiator)
        topic = p.get("topic", "Урегулирование кризиса")
        sec = p.get("secrecy", "Все")
        
        st.session_state.active_conference = {
            "title": title,
            "initiator": initiator,
            "participants": parts,
            "topic": topic,
            "secrecy": sec,
            "stage": "discussion",
            "dialogue": [
                {"speaker": initiator, "text": f"Господа, объявляю саммит «{title}» открытым. Повестка дня: {topic}."}
            ],
            "final_proposal": "",
            "votes": {}
        }
        return f"🏛 [Саммит] Созвана международная конференция: «{title}»"

    return None

def execute_command_pipeline(commands_list: list) -> list:
    logs = []
    if not isinstance(commands_list, list):
        return ["Предупреждение: список команд пуст."]
        
    for item in commands_list:
        if isinstance(item, dict):
            c_name = item.get("command")
            params = item.get("params", {})
            if c_name:
                res_log = execute_single_command(c_name, params)
                if res_log:
                    logs.append(res_log)
    return logs