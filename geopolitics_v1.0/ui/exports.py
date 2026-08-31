import streamlit as st

def generate_raw_game_log_txt() -> str:
    lines = [
        f"==================================================",
        f"ПОЛНЫЙ СТЕНОГРАФИЧЕСКИЙ ЛОГ ПАРТИИ: {st.session_state.player_country}",
        f"Сценарий: {st.session_state.get('scenario_name', 'Сценарий')} | Сложность: {st.session_state.difficulty} | Хаос: {st.session_state.solar_activity}/10",
        f"==================================================\n"
    ]
    
    # 1. Хроника ходов
    for arch in st.session_state.turn_archives:
        t, d = arch['turn'], arch['date']
        lines.append(f"==================== ХОД {t} ({d}) ====================")
        orders = arch.get("player_orders_raw", "Указов не зафиксировано")
        lines.append(f"\n[УКАЗЫ И ПРИКАЗЫ ПРАВИТЕЛЯ НА ХОД {t}]:\n{orders}\n")
        if arch.get("player_events"):
            lines.append("[ДЕЙСТВИЯ И РЕЗУЛЬТАТЫ СТРАНЫ]:")
            for pe in arch["player_events"]: lines.append(f"  • {pe['title']}: {pe['desc']}")
        if arch.get("world_events"):
            lines.append("\n[МИРОВЫЕ СОБЫТИЯ]:")
            for we in arch["world_events"]: lines.append(f"  • [{we.get('date', d)}] {we['title']}: {we['desc']}")
        if arch.get("press_excerpt"):
            p = arch["press_excerpt"]
            src = p.get("source", "Пресса") if isinstance(p, dict) else "Мировая пресса"
            quote = p.get("quote", "") if isinstance(p, dict) else str(p)
            lines.append(f"\n[ЗАРУБЕЖНАЯ ПРЕССА]: {src} — «{quote}»")
        lines.append("\n")
        
    # 2. Двусторонняя дипломатия
    lines.append("==================== ДВУСТОРОННИЙ ДИПЛОМАТИЧЕСКИЙ АРХИВ ====================")
    for c_key, msgs in st.session_state.chats.items():
        if msgs:
            lines.append(f"\n--- Переписка: {c_key} ---")
            for m in msgs: lines.append(f"[{m['from']}]: {m['text']}")

    # 3. Международные саммиты и круглые столы (НОВОЕ)
    all_confs = list(st.session_state.get("conference_archives", []))
    if st.session_state.get("active_conference"):
        all_confs.append(st.session_state.active_conference)
        
    if all_confs:
        lines.append("\n==================== МЕЖДУНАРОДНЫЕ САММИТЫ И КОНФЕРЕНЦИИ ====================")
        for conf in all_confs:
            lines.append(f"\n--- САММИТ: «{conf['title']}» (Статус: {conf.get('status', 'В процессе')}) ---")
            lines.append(f"Инициатор: {conf['initiator']} | Режим: {conf.get('secrecy', 'Публичный')}")
            lines.append(f"Участники: {', '.join(conf.get('participants', []))}")
            lines.append(f"Повестка дня: {conf.get('topic', '')}\n")
            
            lines.append("[СТЕНОГРАММА КРУГЛОГО СТОЛА]:")
            for sp in conf.get("dialogue", []):
                lines.append(f"  • {sp.get('speaker')}: {sp.get('text')}")
                
            if conf.get("positions_summary"):
                lines.append(f"\n[ПОЗИЦИИ СТОРОН И СПОРЫ]:\n{conf['positions_summary']}")
                
            if conf.get("votes"):
                lines.append("\n[ПОИМЕННЫЕ ГОЛОСА ПО РЕЗОЛЮЦИИ]:")
                for c_v, v_d in conf["votes"].items():
                    lines.append(f"  • {c_v}: [{v_d.get('vote')}] — {v_d.get('reason')}")
                    
            lines.append(f"\n[ИТОГОВЫЙ ВЕРДИКТ / РЕЗОЛЮЦИЯ]:\n{conf.get('summary', 'Решение вырабатывается')}")
            if conf.get("minister_debrief"):
                lines.append(f"\n[АНАЛИТИЧЕСКАЯ ЗАПИСКА МИД]:\n{conf['minister_debrief']}")
            lines.append("-" * 60)
                
    # 4. Советники
    lines.append("\n==================== СТЕНОГРАММЫ СОВЕТНИКОВ ====================")
    for role, msgs in st.session_state.advisor_chats.items():
        lines.append(f"\n--- Ведомство: {role} ---")
        for m in msgs: lines.append(f"[{m['role'].upper()}]: {m['content']}")
            
    return "\n".join(lines)

def generate_newspaper_html() -> str:
    my_c = st.session_state.countries[st.session_state.player_country]
    my_mil = my_c.get("military", {})
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Хроника эпохи: {st.session_state.player_country}</title>
<style>
body {{ font-family: 'Georgia', serif; background-color: #f4f1ea; color: #1a1a1a; padding: 25px; line-height: 1.6; max-width: 1000px; margin: auto; }}
h1 {{ text-align: center; border-bottom: 3px double #333; padding-bottom: 10px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; }}
h2 {{ border-bottom: 2px solid #8b0000; padding-bottom: 5px; color: #8b0000; margin-top: 35px; text-transform: uppercase; }}
.meta {{ text-align: center; font-style: italic; color: #555; margin-bottom: 30px; }}
.turn-block {{ background: #fff; padding: 20px; margin-bottom: 25px; border: 1px solid #dcd7cb; box-shadow: 2px 2px 6px rgba(0,0,0,0.06); }}
.turn-header {{ font-size: 1.3em; font-weight: bold; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-bottom: 15px; color: #8b0000; }}
.section-title {{ font-size: 1.1em; font-weight: bold; margin-top: 15px; color: #333; text-transform: uppercase; }}
.event {{ margin-bottom: 10px; padding-left: 10px; border-left: 3px solid #666; }}
.press-quote {{ background: #fdfbf7; border-left: 3px solid #b8860b; padding: 10px; font-style: italic; margin-top: 15px; }}
.chat-msg {{ padding: 6px 10px; margin-bottom: 6px; border-radius: 4px; }}
.chat-us {{ background: #e8f5e9; text-align: right; }}
.chat-them {{ background: #e3f2fd; text-align: left; }}
.summit-dialogue {{ background: #f9f9f9; border-left: 4px solid #3b82f6; padding: 10px; margin: 10px 0; font-size: 0.95em; }}
.vote-badge-yes {{ color: #15803d; font-weight: bold; }}
.vote-badge-no {{ color: #b91c1c; font-weight: bold; }}
.vote-badge-abs {{ color: #4b5563; font-style: italic; }}
.minister-box {{ background: #fefce8; border: 1px solid #fef08a; padding: 12px; margin-top: 10px; font-style: italic; border-left: 4px solid #ca8a04; }}
</style>
</head>
<body>
<h1>Вестник Мировой Истории</h1>
<div class="meta">Летопись правления державы: <b>{st.session_state.player_country}</b> | Дата: {st.session_state.current_date} | Ход: {st.session_state.turn}</div>

<h2>📰 Хроника ходов и мировых событий</h2>
"""
    for arch in st.session_state.turn_archives:
        html += f"""<div class="turn-block">
<div class="turn-header">Ход {arch['turn']} — {arch['date']}</div>"""
        if arch.get("player_events"):
            html += '<div class="section-title">🏛 Государственные указы и последствия:</div>'
            for pe in arch["player_events"]: html += f'<div class="event"><b>{pe["title"]}</b><br>{pe["desc"]}</div>'
        if arch.get("world_events"):
            html += '<div class="section-title">🌍 Международные депеши:</div>'
            for we in arch["world_events"]: html += f'<div class="event"><b>[{we.get("date", arch["date"])}] {we["title"]}</b><br>{we["desc"]}</div>'
        if arch.get("press_excerpt"):
            p = arch["press_excerpt"]
            src = p.get("source", "Пресса") if isinstance(p, dict) else "Мировая пресса"
            quote = p.get("quote", "") if isinstance(p, dict) else str(p)
            if quote: html += f'<div class="press-quote">🗞 <b>{src}:</b> «{quote}»</div>'
        html += '</div>'

    # Международные саммиты в HTML
    all_confs = list(st.session_state.get("conference_archives", []))
    if st.session_state.get("active_conference"):
        all_confs.append(st.session_state.active_conference)
        
    if all_confs:
        html += "<h2>🏛 Международные Саммиты и Мирные Конференции</h2>"
        for conf in all_confs:
            status_cls = "color: green;" if conf.get("passed") else "color: #b91c1c;"
            html += f"""<div class="turn-block">
<h3>Саммит: «{conf['title']}» <span style="{status_cls}">[{conf.get('status', 'Завершен')}]</span></h3>
<p><b>Инициатор:</b> {conf['initiator']} | <b>Участники:</b> {', '.join(conf.get('participants', []))} | <b>Секретность:</b> {conf.get('secrecy', 'Публичный')}</p>
<p><b>Повестка дня:</b> {conf.get('topic', '')}</p>

<div class="section-title">📜 Стенограмма круглого стола:</div>
<div class="summit-dialogue">"""
            for sp in conf.get("dialogue", []):
                html += f"<p><b>{sp.get('speaker')}:</b> {sp.get('text')}</p>"
            html += "</div>"

            if conf.get("positions_summary"):
                html += f"<p><b>Позиции участников:</b> {conf['positions_summary']}</p>"

            if conf.get("votes"):
                html += '<div class="section-title">⚖️ Итоги поименного голосования:</div><ul>'
                for c_v, v_d in conf["votes"].items():
                    v_type = v_d.get("vote", "Воздержался")
                    v_cls = "vote-badge-yes" if v_type == "За" else "vote-badge-no" if v_type == "Против" else "vote-badge-abs"
                    html += f"<li><b>{c_v}:</b> <span class='{v_cls}'>[{v_type}]</span> — <i>{v_d.get('reason', '')}</i></li>"
                html += "</ul>"

            html += f"<p><b>Итоговый вердикт:</b> {conf.get('summary', '')}</p>"

            if conf.get("minister_debrief"):
                html += f"""<div class="minister-box">
<b>Аналитическая записка МИД:</b><br>{conf['minister_debrief']}
</div>"""
            html += "</div>"

    # Дипломатия
    html += "<h2>🤝 Двусторонний дипломатический архив</h2>"
    for c_key, msgs in st.session_state.chats.items():
        if msgs:
            html += f"<div class='turn-block'><h3>Посольство: {c_key}</h3>"
            for m in msgs:
                cls = "chat-us" if m["from"] == st.session_state.player_country else "chat-them"
                html += f"<div class='chat-msg {cls}'><b>{m['from']}:</b> {m['text']}</div>"
            html += "</div>"

    # Вооружение
    html += "<h2>🪖 Реестр Вооруженных Сил</h2><div class='turn-block'>"
    if isinstance(my_mil, dict):
        for cat, items in my_mil.items():
            html += f"<h4>Категория: {cat.upper()}</h4><ul>"
            for it in items:
                status = "В строю" if it.get("in_service") else "На консервации"
                html += f"<li><b>{it['name']}</b> ({it.get('count', 0):,} ед. [{status}]) — <i>{it.get('specs', '')}</i></li>"
            html += "</ul>"
    html += "</div></body></html>"
    return html