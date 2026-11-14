import html as _html
import streamlit as st

from core.world_ops import to_int


def _e(value) -> str:
    """Всё, что пришло от ИИ или игрока, экранируется: иначе «<» и «&» ломают HTML-хронику."""
    return _html.escape(str(value))


def _press(arch):
    """(источник, цитата) или None."""
    p = arch.get("press_excerpt")
    if not p:
        return None
    src = p.get("source", "Пресса") if isinstance(p, dict) else "Мировая пресса"
    quote = p.get("quote", "") if isinstance(p, dict) else str(p)
    return (src, quote) if quote else None


def _all_conferences() -> list:
    confs = list(st.session_state.get("conference_archives", []))
    if st.session_state.get("active_conference"):
        confs.append(st.session_state.active_conference)
    return confs


def generate_raw_game_log_txt() -> str:
    ss = st.session_state
    lines = [
        "==================================================",
        f"ПОЛНЫЙ СТЕНОГРАФИЧЕСКИЙ ЛОГ ПАРТИИ: {ss.player_country}",
        f"Сценарий: {ss.get('scenario_name', 'Сценарий')} | Сложность: {ss.difficulty} | Хаос: {ss.solar_activity}/10",
        "==================================================\n"
    ]

    # 1. Хроника ходов
    for arch in ss.turn_archives:
        t, d = arch.get("turn"), arch.get("date")
        lines.append(f"==================== ХОД {t} ({d}) ====================")
        lines.append(f"\n[УКАЗЫ И ПРИКАЗЫ ПРАВИТЕЛЯ НА ХОД {t}]:\n{arch.get('player_orders_raw', 'Указов не зафиксировано')}\n")
        if arch.get("player_events"):
            lines.append("[ДЕЙСТВИЯ И РЕЗУЛЬТАТЫ СТРАНЫ]:")
            lines += [f"  • {pe.get('title')}: {pe.get('desc')}" for pe in arch["player_events"]]
        if arch.get("world_events"):
            lines.append("\n[МИРОВЫЕ СОБЫТИЯ]:")
            lines += [f"  • [{we.get('date', d)}] {we.get('title')}: {we.get('desc')}" for we in arch["world_events"]]
        press = _press(arch)
        if press:
            lines.append(f"\n[ЗАРУБЕЖНАЯ ПРЕССА]: {press[0]} — «{press[1]}»")
        lines.append("\n")

    # 2. Двусторонняя дипломатия
    lines.append("==================== ДВУСТОРОННИЙ ДИПЛОМАТИЧЕСКИЙ АРХИВ ====================")
    for c_key, msgs in ss.chats.items():
        if msgs:
            lines.append(f"\n--- Переписка: {c_key} ---")
            lines += [f"[{m.get('from')}]: {m.get('text')}" for m in msgs]

    # 3. Международные саммиты и круглые столы
    confs = _all_conferences()
    if confs:
        lines.append("\n==================== МЕЖДУНАРОДНЫЕ САММИТЫ И КОНФЕРЕНЦИИ ====================")
        for conf in confs:
            lines.append(f"\n--- САММИТ: «{conf.get('title')}» (Статус: {conf.get('status', 'В процессе')}) ---")
            lines.append(f"Инициатор: {conf.get('initiator')} | Режим: {conf.get('secrecy', 'Публичный')}")
            lines.append(f"Участники: {', '.join(conf.get('participants', []))}")
            lines.append(f"Повестка дня: {conf.get('topic', '')}\n")
            lines.append("[СТЕНОГРАММА КРУГЛОГО СТОЛА]:")
            lines += [f"  • {sp.get('speaker')}: {sp.get('text')}" for sp in conf.get("dialogue", [])]
            if conf.get("positions_summary"):
                lines.append(f"\n[ПОЗИЦИИ СТОРОН И СПОРЫ]:\n{conf['positions_summary']}")
            if conf.get("votes"):
                lines.append("\n[ПОИМЕННЫЕ ГОЛОСА ПО РЕЗОЛЮЦИИ]:")
                lines += [f"  • {c_v}: [{v_d.get('vote')}] — {v_d.get('reason')}" for c_v, v_d in conf["votes"].items()]
            lines.append(f"\n[ИТОГОВЫЙ ВЕРДИКТ / РЕЗОЛЮЦИЯ]:\n{conf.get('summary', 'Решение вырабатывается')}")
            if conf.get("minister_debrief"):
                lines.append(f"\n[АНАЛИТИЧЕСКАЯ ЗАПИСКА МИД]:\n{conf['minister_debrief']}")
            lines.append("-" * 60)

    # 4. Советники
    lines.append("\n==================== СТЕНОГРАММЫ СОВЕТНИКОВ ====================")
    for role, msgs in ss.get("advisor_chats", {}).items():
        lines.append(f"\n--- Ведомство: {role} ---")
        lines += [f"[{str(m.get('role', '')).upper()}]: {m.get('content')}" for m in msgs]

    return "\n".join(lines)


def generate_newspaper_html() -> str:
    ss = st.session_state
    me = ss.player_country
    my_mil = ss.countries[me].get("military")

    out = [f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Хроника эпохи: {_e(me)}</title>
<style>__CSS__</style>
</head>
<body>
<h1>Вестник Мировой Истории</h1>
<div class="meta">Летопись правления державы: <b>{_e(me)}</b> | Дата: {_e(ss.current_date)} | Ход: {ss.turn}</div>

<h2>📰 Хроника ходов и мировых событий</h2>
"""]
    for arch in ss.turn_archives:
        out.append(f'<div class="turn-block"><div class="turn-header">Ход {_e(arch.get("turn"))} — {_e(arch.get("date"))}</div>')
        if arch.get("player_events"):
            out.append('<div class="section-title">🏛 Государственные указы и последствия:</div>')
            out += [f'<div class="event"><b>{_e(pe.get("title"))}</b><br>{_e(pe.get("desc"))}</div>' for pe in arch["player_events"]]
        if arch.get("world_events"):
            out.append('<div class="section-title">🌍 Международные депеши:</div>')
            out += [f'<div class="event"><b>[{_e(we.get("date", arch.get("date")))}] {_e(we.get("title"))}</b><br>{_e(we.get("desc"))}</div>' for we in arch["world_events"]]
        press = _press(arch)
        if press:
            out.append(f'<div class="press-quote">🗞 <b>{_e(press[0])}:</b> «{_e(press[1])}»</div>')
        out.append("</div>")

    confs = _all_conferences()
    if confs:
        out.append("<h2>🏛 Международные Саммиты и Мирные Конференции</h2>")
        for conf in confs:
            status_cls = "color: green;" if conf.get("passed") else "color: #b91c1c;"
            out.append(f"""<div class="turn-block">
<h3>Саммит: «{_e(conf.get('title'))}» <span style="{status_cls}">[{_e(conf.get('status', 'Завершен'))}]</span></h3>
<p><b>Инициатор:</b> {_e(conf.get('initiator'))} | <b>Участники:</b> {_e(', '.join(conf.get('participants', [])))} | <b>Секретность:</b> {_e(conf.get('secrecy', 'Публичный'))}</p>
<p><b>Повестка дня:</b> {_e(conf.get('topic', ''))}</p>
<div class="section-title">📜 Стенограмма круглого стола:</div>
<div class="summit-dialogue">""")
            out += [f"<p><b>{_e(sp.get('speaker'))}:</b> {_e(sp.get('text'))}</p>" for sp in conf.get("dialogue", [])]
            out.append("</div>")
            if conf.get("positions_summary"):
                out.append(f"<p><b>Позиции участников:</b> {_e(conf['positions_summary'])}</p>")
            if conf.get("votes"):
                out.append('<div class="section-title">⚖️ Итоги поименного голосования:</div><ul>')
                for c_v, v_d in conf["votes"].items():
                    v_type = v_d.get("vote", "Воздержался")
                    v_cls = "vote-badge-yes" if v_type == "За" else "vote-badge-no" if v_type == "Против" else "vote-badge-abs"
                    out.append(f"<li><b>{_e(c_v)}:</b> <span class='{v_cls}'>[{_e(v_type)}]</span> — <i>{_e(v_d.get('reason', ''))}</i></li>")
                out.append("</ul>")
            out.append(f"<p><b>Итоговый вердикт:</b> {_e(conf.get('summary', ''))}</p>")
            if conf.get("minister_debrief"):
                out.append(f'<div class="minister-box"><b>Аналитическая записка МИД:</b><br>{_e(conf["minister_debrief"])}</div>')
            out.append("</div>")

    out.append("<h2>🤝 Двусторонний дипломатический архив</h2>")
    for c_key, msgs in ss.chats.items():
        if msgs:
            out.append(f"<div class='turn-block'><h3>Посольство: {_e(c_key)}</h3>")
            for m in msgs:
                cls = "chat-us" if m.get("from") == me else "chat-them"
                out.append(f"<div class='chat-msg {cls}'><b>{_e(m.get('from'))}:</b> {_e(m.get('text'))}</div>")
            out.append("</div>")

    out.append("<h2>🪖 Реестр Вооруженных Сил</h2><div class='turn-block'>")
    if isinstance(my_mil, dict):
        for cat, items in my_mil.items():
            out.append(f"<h4>Категория: {_e(cat.upper())}</h4><ul>")
            for it in items:
                status = "В строю" if it.get("in_service", True) else "На консервации"
                out.append(f"<li><b>{_e(it.get('name'))}</b> ({to_int(it.get('count', 0)):,} ед. [{status}]) — <i>{_e(it.get('specs', ''))}</i></li>")
            out.append("</ul>")
    out.append("</div></body></html>")
    return "\n".join(out).replace("__CSS__", CSS, 1)


CSS = """
body { font-family: 'Georgia', serif; background-color: #f4f1ea; color: #1a1a1a; padding: 25px; line-height: 1.6; max-width: 1000px; margin: auto; }
h1 { text-align: center; border-bottom: 3px double #333; padding-bottom: 10px; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 5px; }
h2 { border-bottom: 2px solid #8b0000; padding-bottom: 5px; color: #8b0000; margin-top: 35px; text-transform: uppercase; }
.meta { text-align: center; font-style: italic; color: #555; margin-bottom: 30px; }
.turn-block { background: #fff; padding: 20px; margin-bottom: 25px; border: 1px solid #dcd7cb; box-shadow: 2px 2px 6px rgba(0,0,0,0.06); }
.turn-header { font-size: 1.3em; font-weight: bold; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-bottom: 15px; color: #8b0000; }
.section-title { font-size: 1.1em; font-weight: bold; margin-top: 15px; color: #333; text-transform: uppercase; }
.event { margin-bottom: 10px; padding-left: 10px; border-left: 3px solid #666; }
.press-quote { background: #fdfbf7; border-left: 3px solid #b8860b; padding: 10px; font-style: italic; margin-top: 15px; }
.chat-msg { padding: 6px 10px; margin-bottom: 6px; border-radius: 4px; }
.chat-us { background: #e8f5e9; text-align: right; }
.chat-them { background: #e3f2fd; text-align: left; }
.summit-dialogue { background: #f9f9f9; border-left: 4px solid #3b82f6; padding: 10px; margin: 10px 0; font-size: 0.95em; }
.vote-badge-yes { color: #15803d; font-weight: bold; }
.vote-badge-no { color: #b91c1c; font-weight: bold; }
.vote-badge-abs { color: #4b5563; font-style: italic; }
.minister-box { background: #fefce8; border: 1px solid #fef08a; padding: 12px; margin-top: 10px; font-style: italic; border-left: 4px solid #ca8a04; }
"""
