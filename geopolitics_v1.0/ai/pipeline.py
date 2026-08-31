import copy
import streamlit as st
from ai.client import get_ai_client, load_config
from ai.agents.arbiter import agent_internal_arbiter
from ai.agents.world import agent_world_simulator
from ai.agents.diplomacy import agent_diplomacy
from ai.agents.architect import agent_geopolitical_architect
from ai.agents.vpk import agent_military_industrial_complex
from ai.agents.auditor import agent_supreme_inspector_auditor
from core.state import GAME_STATE_KEYS, save_game_to_slot
from core.procedural_sim import run_procedural_background_noise
from core.military import get_smart_fallback_military

def process_turn_pipeline(orders_current: str):
    cfg = load_config()
    if not cfg.get("api_key"):
        st.error("Укажите API Key в настройках!")
        return

    cl = get_ai_client(cfg["api_key"], cfg["base_url"])
    m_name = cfg["model_name"]
    
    with st.status("Многоагентный конвейер ИИ обрабатывает ход...", expanded=True) as status:
        # Сохранение снимка истории для отката
        hist_item = {k: copy.deepcopy(st.session_state[k]) for k in GAME_STATE_KEYS if k in st.session_state}
        st.session_state.history.append(hist_item)
        
        # 3-уровневый горизонт: последние 3 заголовка
        recent_titles = []
        for arch in st.session_state.turn_archives[-3:]:
            for we in arch.get("world_events", []):
                recent_titles.append(we.get("title", ""))

        common_state = {
            "turn": st.session_state.turn,
            "current_date": st.session_state.current_date,
            "player_country": st.session_state.player_country,
            "difficulty": st.session_state.difficulty,
            "solar_activity": st.session_state.solar_activity,
            "is_alt_history": st.session_state.get("is_alt_history", False),
            "my_country": st.session_state.countries[st.session_state.player_country],
            "countries": st.session_state.countries,
            "rd_projects": st.session_state.rd_projects,
            "ongoing_arcs": st.session_state.ongoing_arcs
        }
        
        turn_tokens = 0
        
        # 1. Агент 1: Внутренний арбитр
        st.write("1/6 [Агент 1] Внутренний арбитр рассчитывает законы и стабильность...")
        res_internal, t1 = agent_internal_arbiter(cl, m_name, common_state, orders_current)
        turn_tokens += t1
        if "updated_ongoing_arcs" in res_internal:
            st.session_state.ongoing_arcs = res_internal["updated_ongoing_arcs"]
        
        # 2. Агент 2: Мировой симулятор (Автономная жизнь мира)
        st.write(f"2/6 [Агент 2] Мировой симулятор генерирует новости ({'Будильник: 4 региона' if st.session_state.alarm_clock_active else 'Стандарт'})...")
        res_world, t2 = agent_world_simulator(cl, m_name, common_state, orders_current, recent_titles, st.session_state.alarm_clock_active)
        turn_tokens += t2
        
        # 3. Агент 3: Дипломатия
        st.write("3/6 [Агент 3] Дипломатический корпус готовит депеши лидеров...")
        res_diplo, t3 = agent_diplomacy(cl, m_name, common_state, st.session_state.pending_diplo)
        turn_tokens += t3
        
        # 4. Агент 4: Архитектор геополитики
        st.write("4/6 [Агент 4] Архитектор проверяет границы и альянсы...")
        res_borders, t4 = agent_geopolitical_architect(cl, m_name, common_state)
        turn_tokens += t4
        
        # 5. Агент 5: Министр ВПК и Полигон
        st.write("5/6 [Агент 5] Министр ВПК рассчитывает выпуск техники и испытания в КБ...")
        res_vpk, t5 = agent_military_industrial_complex(cl, m_name, common_state, orders_current)
        turn_tokens += t5
        
        # 6. Агент 6: Ревизор и Верховный арбитр
        st.write("6/6 [Агент 6] Верховный Ревизор сверяет точность исполнения указов...")
        proposed_pkg = {
            "internal": res_internal,
            "world": res_world,
            "vpk": res_vpk
        }
        res_inspector, t6 = agent_supreme_inspector_auditor(cl, m_name, common_state, orders_current, proposed_pkg)
        turn_tokens += t6
        
        if not res_inspector.get("approved", True):
            patches = res_inspector.get("correction_patches", {})
            if patches.get("adjust_stability") is not None:
                res_internal.setdefault("updated_stats", {})["stability"] = patches["adjust_stability"]
            if patches.get("add_missing_event"):
                res_internal.setdefault("new_player_events", []).append(patches["add_missing_event"])
                
        # 7. Фоновый математический шум (0 токенов)
        run_procedural_background_noise(st.session_state.countries, st.session_state.player_country, st.session_state.turn)
        
        status.update(label=f"Ход успешно обработан! Ревизия: {res_inspector.get('audit_notes', 'Одобрено')}", state="complete")

    st.session_state.token_usage["turn"] = turn_tokens
    st.session_state.token_usage["total"] += turn_tokens
    
    # Применение обновлений
    if res_world.get("new_date"):
        st.session_state.current_date = res_world["new_date"]
        
    st.session_state.turn_archives.append({
        "turn": st.session_state.turn + 1,
        "date": st.session_state.current_date,
        "player_orders_raw": orders_current if orders_current else "Нет прямых приказов",
        "world_events": res_world.get("new_world_events", []),
        "flavor_events": res_world.get("flavor_events", []),
        "player_events": res_internal.get("new_player_events", []),
        "press_excerpt": res_internal.get("press_excerpt")
    })
    
    my_c = st.session_state.countries[st.session_state.player_country]
    if "updated_stats" in res_internal:
        my_c["stats"].update(res_internal["updated_stats"])
    if "updated_issues" in res_internal:
        my_c["current_issues"] = res_internal["updated_issues"]
    st.session_state.internal_events = res_internal.get("new_internal_events", [])
    
    if "diplo_responses" in res_diplo:
        for d_resp in res_diplo["diplo_responses"]:
            f_c, t_c = d_resp["from"], d_resp["to"]
            c_key = f"{min(f_c, t_c)}-{max(f_c, t_c)}"
            if c_key not in st.session_state.chats: st.session_state.chats[c_key] = []
            st.session_state.chats[c_key].append({"from": f_c, "text": d_resp["message"]})
            if f_c != st.session_state.player_country:
                st.session_state.unread_messages.add(f_c)
                
    if "updated_rd_projects" in res_vpk:
        st.session_state.rd_projects = res_vpk["updated_rd_projects"]
        
    if "production_increments" in res_vpk:
        for inc in res_vpk["production_increments"]:
            cat_target = inc.get("category")
            name_target = inc.get("name")
            add_amt = inc.get("added_count", 0)
            if cat_target in my_c.get("military", {}):
                for eq_item in my_c["military"][cat_target]:
                    if eq_item.get("name") == name_target and eq_item.get("production", False):
                        eq_item["count"] = eq_item.get("count", 0) + max(0, add_amt)
                        
    if "country_transformations" in res_borders:
        for trans in res_borders["country_transformations"]:
            hide_c = trans.get("hide_country")
            if hide_c and hide_c in st.session_state.countries:
                st.session_state.countries[hide_c]["status"] = "Спящая"
            for sp in trans.get("spawn_countries", []):
                sp_name = sp.get("name", "Новое Государство")
                st.session_state.countries[sp_name] = {
                    "status": "Активная",
                    "is_great_power": sp.get("is_great_power", False),
                    "regime": sp.get("regime", "Временное правительство"),
                    "region": sp.get("region", "Европа"),
                    "faction": "Нет", "overlord": None,
                    "resources": "Ограниченные резервы",
                    "stats": sp.get("stats", {"stability": 50, "war_support": 70, "military_readiness": 50, "manpower_approx": "~300 тыс. чел."}),
                    "current_issues": [{"name": "Гражданская война", "start_date": st.session_state.current_date, "target_date": "1 Год", "status": "Острая фаза"}],
                    "relations": {},
                    "military": get_smart_fallback_military(sp_name, st.session_state.current_date)
                }
                if hide_c:
                    old_k = f"{min(st.session_state.player_country, hide_c)}-{max(st.session_state.player_country, hide_c)}"
                    new_k = f"{min(st.session_state.player_country, sp_name)}-{max(st.session_state.player_country, sp_name)}"
                    st.session_state.chats[new_k] = copy.deepcopy(st.session_state.chats.get(old_k, []))

    st.session_state.pending_diplo = []
    st.session_state.turn += 1
    
    if st.session_state.turn % st.session_state.autosave_interval == 0:
        save_game_to_slot(st.session_state.current_slot)
        
    st.rerun()