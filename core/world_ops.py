"""Общие операции над миром: страны, дипломатические чаты, события, саммиты.

Раньше та же логика была скопирована в commands.py, engine.py, pipeline.py и вкладках UI.
"""
import streamlit as st

STAT_KEYS = ("stability", "war_support", "military_readiness")


# --------------------------------------------------------------------------- #
# Санитайзеры для всего, что приходит от LLM
# --------------------------------------------------------------------------- #
def clamp_stat(value, default=50) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return default


def to_int(value, default=0, lo=0) -> int:
    """'1 500', '~200', 1500.0 -> int. Мусор -> default."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(lo, int(value))
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return max(lo, int(digits)) if digits else default


def clean_events(items, with_date=False) -> list:
    """Список событий [{title, desc[, date]}] без мусора."""
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict) or not (it.get("title") or it.get("desc")):
            continue
        ev = {"title": str(it.get("title") or "Событие"), "desc": str(it.get("desc") or "")}
        if with_date:
            ev["date"] = str(it.get("date") or st.session_state.get("current_date", ""))
        out.append(ev)
    return out


def clean_stats_patch(d) -> dict:
    d = d if isinstance(d, dict) else {}
    patch = {}
    for k in STAT_KEYS:
        if k in d and d[k] is not None:
            try:
                patch[k] = max(0, min(100, int(float(d[k]))))
            except (TypeError, ValueError):
                pass
    if d.get("manpower_approx"):
        patch["manpower_approx"] = str(d["manpower_approx"])
    return patch


# --------------------------------------------------------------------------- #
# Страны
# --------------------------------------------------------------------------- #
def new_country(name: str, data: dict = None) -> dict:
    """Единый шаблон страны (понимает и плоские ключи команд, и вложенные stats агентов)."""
    d = data if isinstance(data, dict) else {}
    s = d.get("stats") if isinstance(d.get("stats"), dict) else {}
    mil = d.get("military")
    return {
        "status": "Активная",
        "is_great_power": bool(d.get("is_great_power", False)),
        "regime": str(d.get("regime") or "Республика"),
        "faction": str(d.get("faction") or "Нет"),
        "region": str(d.get("region") or "Европа"),
        "ambitions": str(d.get("ambitions") or "Сохранение суверенитета и порядка."),
        "fears": str(d.get("fears") or "Внешняя агрессия."),
        "overlord": d.get("overlord"),
        "resources": str(d.get("resources") or "Местные резервы"),
        "stats": {
            "stability": clamp_stat(d.get("stability", s.get("stability")), 60),
            "war_support": clamp_stat(d.get("war_support", s.get("war_support")), 30),
            "military_readiness": clamp_stat(d.get("military_readiness", s.get("military_readiness")), 40),
            "manpower_approx": str(d.get("manpower") or d.get("manpower_approx")
                                   or s.get("manpower_approx") or "~100 тыс. чел."),
        },
        "profile": str(d.get("profile") or "Суверенное государство."),
        "current_issues": d.get("current_issues") if isinstance(d.get("current_issues"), list) else [],
        "relations": d.get("relations") if isinstance(d.get("relations"), dict) else {},
        "military": mil if isinstance(mil, dict) else None,   # None = реестр ещё не сформирован
    }


def resolve_country(name):
    """Название от ИИ/игрока -> точное имя страны из мира (или None)."""
    if not name:
        return None
    countries = st.session_state.countries
    name = str(name).strip()
    if name in countries:
        return name
    low = name.casefold()
    for c in countries:
        if c.casefold() == low:
            return c
    near = [c for c in countries if low in c.casefold() or c.casefold() in low]
    return near[0] if len(near) == 1 else None


# --------------------------------------------------------------------------- #
# Дипломатические чаты. Ключ = «A-B» (имена по алфавиту) — формат старых сохранений.
# --------------------------------------------------------------------------- #
def chat_key(a: str, b: str) -> str:
    x, y = sorted((a, b))
    return f"{x}-{y}"


def chat_other(key: str, name: str):
    """Второй участник чата `key` относительно `name` (или None, если name в чате не участвует)."""
    if key.startswith(name + "-"):
        return key[len(name) + 1:]
    if key.endswith("-" + name):
        return key[:-(len(name) + 1)]
    return None


def drop_chats(name: str):
    for key in [k for k in st.session_state.chats if chat_other(k, name) is not None]:
        del st.session_state.chats[key]


def rename_in_chats(old: str, new: str):
    chats = st.session_state.chats
    for key in list(chats):
        other = chat_other(key, old)
        if other is None:
            continue
        msgs = chats.pop(key)
        for m in msgs:
            if m.get("from") == old:
                m["from"] = new
        chats.setdefault(chat_key(new, other), []).extend(msgs)


def rename_country(old: str, new: str) -> bool:
    ss = st.session_state
    new = str(new or "").strip()
    if old not in ss.countries or not new or new in ss.countries:
        return False
    ss.countries[new] = ss.countries.pop(old)
    if ss.player_country == old:
        ss.player_country = new
    if ss.get("diplo_target_country") == old:
        ss.diplo_target_country = new
    rename_in_chats(old, new)
    if old in ss.unread_messages:
        ss.unread_messages.discard(old)
        ss.unread_messages.add(new)
    for d in ss.pending_diplo:
        for k in ("from", "to"):
            if d.get(k) == old:
                d[k] = new
    conf = ss.get("active_conference")
    if conf:
        conf["participants"] = [new if p == old else p for p in conf["participants"]]
        if conf.get("initiator") == old:
            conf["initiator"] = new
    for c in ss.countries.values():
        if c.get("overlord") == old:
            c["overlord"] = new
        rel = c.get("relations")
        if isinstance(rel, dict) and old in rel:
            rel[new] = rel.pop(old)
    return True


def delete_country(name: str) -> bool:
    ss = st.session_state
    if name not in ss.countries:
        return False
    del ss.countries[name]
    drop_chats(name)
    ss.unread_messages.discard(name)
    return True


# --------------------------------------------------------------------------- #
# События и саммиты
# --------------------------------------------------------------------------- #
def current_archive() -> dict:
    """Архив текущего хода (создаёт пустой, если журнал пуст)."""
    ss = st.session_state
    if not ss.get("turn_archives"):
        ss.turn_archives = [{"turn": ss.get("turn", 1), "date": ss.get("current_date", ""),
                             "player_orders_raw": "—", "world_events": [], "flavor_events": [],
                             "player_events": [], "press_excerpt": None}]
    return ss.turn_archives[-1]


def add_world_event(title: str, desc: str):
    current_archive().setdefault("world_events", []).append(
        {"date": st.session_state.current_date, "title": str(title), "desc": str(desc)})


def add_arc(text: str, limit: int = 25):
    """Сюжетная нить для всех агентов. Список ограничен, иначе он раздувает каждый промпт."""
    arcs = st.session_state.ongoing_arcs
    arcs.append(str(text))
    del arcs[:-limit]


def new_conference(title, initiator, participants, topic, secrecy="Все") -> dict:
    parts = list(dict.fromkeys([initiator] + list(participants)))
    return {
        "title": title, "initiator": initiator, "participants": parts, "topic": topic,
        "secrecy": secrecy, "stage": "discussion",
        "dialogue": [{"speaker": initiator,
                      "text": f"Господа, объявляю саммит «{title}» открытым. Повестка дня: {topic}"}],
        "final_proposal": "", "votes": {},
    }
