"""Веб-интерфейс «стол». Запуск: python server.py  (браузер откроется сам).

Только стандартная библиотека. Слушает исключительно 127.0.0.1. Игра хранится в памяти процесса,
сохранения лежат в saves/ как и раньше.
"""
import argparse
import json
import mimetypes
import os
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

if sys.version_info < (3, 9):
    sys.exit("Нужен Python 3.9 или новее (у вас " + sys.version.split()[0] + ").")

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from core import headless  # noqa: E402
headless.install()          # подставной streamlit — ДО импорта остального ядра

from core import army, diplomacy, summit  # noqa: E402
from core import game as G  # noqa: E402
from core import uiprefs  # noqa: E402
from core import state as S  # noqa: E402
from ui import exports  # noqa: E402

WEB_DIR = os.path.join(ROOT, "web")
FONT_MIME = {".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2"}
RAW_ROUTES = {"/api/fonts/upload"}      # тело — сам файл, а не JSON
DEFAULT_PORT = 8765
MAX_BODY = 30 * 1024 * 1024
CSRF_HEADER = ("X-Requested-With", "geo-table")
LOCK = threading.RLock()

ROUTES = {}      # (метод, путь) -> функция(body, query)


class Raw:
    """Ответ-файл (экспорт, скачивание сохранения)."""
    def __init__(self, data, content_type, filename):
        self.data, self.content_type, self.filename = data.encode("utf-8"), content_type, filename


def route(method, path):
    def deco(fn):
        ROUTES[(method, path)] = fn
        return fn
    return deco


def q(query, key, default=None):
    return query.get(key, [default])[0]


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@route("GET", "/api/state")
def api_state(body, query):
    ph = G.phase()
    out = {"phase": ph, "busy": G.TURN.running, "config": G.config_public()}
    if ph in ("game", "successor") and not G.TURN.running:
        out["hud"] = G.hud()
    if ph == "successor":
        out["candidates"] = G.successor_candidates()
    return out


@route("GET", "/api/menu")
def api_menu(body, query):
    return {"slots": G.list_slots(), "scenarios": G.list_scenarios()}


@route("GET", "/api/scenario")
def api_scenario(body, query):
    return {"countries": G.scenario_countries(q(query, "file", ""))}


@route("POST", "/api/menu/start")
def api_start(body, query):
    G.start_new_game(body.get("slot"), body.get("file", ""), body.get("country", ""),
                     body.get("difficulty", "Нормальный"), body.get("solar", 2))
    return {"ok": True}


@route("POST", "/api/menu/load")
def api_load(body, query):
    G.load_slot(body.get("slot"))
    return {"ok": True}


@route("POST", "/api/menu/delete")
def api_delete(body, query):
    G.delete_slot(body.get("slot"))
    return {"ok": True}


@route("POST", "/api/menu/import")
def api_import(body, query):
    G.import_slot(body.get("slot"), body.get("data"))
    return {"ok": True}


@route("GET", "/api/menu/download")
def api_download(body, query):
    slot = int(q(query, "slot", 0))
    info = S.get_slot_info(slot)
    if not info.get("exists"):
        raise G.GameError("Ячейка пуста")
    return Raw(G.slot_file(slot), "application/json", f"slot_{slot}_{info['country']}.json")


@route("POST", "/api/successor")
def api_successor(body, query):
    G.choose_successor(body.get("name"))
    return {"ok": True}


@route("GET", "/api/news")
def api_news(body, query):
    t = q(query, "turn")
    return G.news(int(t) if t else None)


@route("GET", "/api/news/index")
def api_news_index(body, query):
    return {"turns": G.news_index()}


@route("GET", "/api/agenda")
def api_agenda(body, query):
    return G.agenda()


@route("POST", "/api/event/dismiss")
def api_dismiss(body, query):
    G.dismiss_event(body.get("index", -1))
    return G.agenda()


@route("GET", "/api/orders")
def api_orders_get(body, query):
    return {"text": G.get_orders(), "turn": G.hud()["turn"], "date": G.hud()["date"]}


@route("POST", "/api/orders")
def api_orders_set(body, query):
    G.set_orders(body.get("text", ""))
    return {"ok": True}


@route("GET", "/api/notes")
def api_notes_get(body, query):
    return G.notes()


@route("POST", "/api/notes")
def api_notes_set(body, query):
    G.note_set(body.get("page", 1), body.get("text"), body.get("title"))
    return {"ok": True}


@route("GET", "/api/gm")
def api_gm_get(body, query):
    return {"messages": G.st.session_state.gm_chat[-60:]}


@route("POST", "/api/gm")
def api_gm_send(body, query):
    G.gm_send(str(body.get("text", ""))[:2000])
    return {"messages": G.st.session_state.gm_chat[-60:], "hud": G.hud()}


@route("GET", "/api/config")
def api_config(body, query):
    return G.config_public()


@route("POST", "/api/config")
def api_config_set(body, query):
    G.config_update(body.get("api_key"), body.get("base_url"), body.get("model_name"), body.get("theme"))
    return G.config_public()


@route("POST", "/api/config/test")
def api_config_test(body, query):
    return G.config_test()


@route("POST", "/api/settings")
def api_settings(body, query):
    if "autosave" in body:
        G.set_autosave(body["autosave"])
    if "alarm" in body:
        G.set_alarm(body["alarm"])
    return G.hud()


@route("POST", "/api/rollback")
def api_rollback(body, query):
    if not G.rollback():
        raise G.GameError("История ходов пуста")
    return G.hud()


@route("POST", "/api/redo")
def api_redo(body, query):
    if not G.redo():
        raise G.GameError("Вперёд идти некуда")
    return G.hud()


@route("POST", "/api/save")
def api_save(body, query):
    G.save_now()
    return {"ok": True}


@route("POST", "/api/exit")
def api_exit(body, query):
    G.exit_to_menu()
    return {"ok": True}


@route("GET", "/api/export/log")
def api_export_log(body, query):
    return Raw(exports.generate_raw_game_log_txt(), "text/plain", "game_log.txt")


@route("GET", "/api/export/newspaper")
def api_export_news(body, query):
    return Raw(exports.generate_newspaper_html(), "text/html", "chronicle.html")


@route("GET", "/api/turn/precheck")
def api_precheck(body, query):
    return {"warnings": G.end_turn_warnings()}


@route("POST", "/api/turn/start")
def api_turn_start(body, query):
    if "orders" in body:
        G.set_orders(body["orders"])
    if not G.config_public()["has_key"]:
        raise G.GameError("Укажите API-ключ в настройках (телефон)")
    if not G.TURN.start():
        raise G.GameError("Ход уже обрабатывается")
    return {"ok": True}


@route("GET", "/api/turn/status")
def api_turn_status(body, query):
    return G.TURN.status()


# ---- дипломатия и советники ----
@route("GET", "/api/diplo/contacts")
def api_contacts(body, query):
    return {"contacts": diplomacy.contacts()}


@route("GET", "/api/diplo/chat")
def api_diplo_chat(body, query):
    return diplomacy.chat(q(query, "country", ""))


@route("POST", "/api/diplo/send")
def api_diplo_send(body, query):
    diplomacy.send(body.get("country"), body.get("text"))
    return {**diplomacy.chat(body.get("country")), "hud": G.hud()}


@route("GET", "/api/advisors/chat")
def api_adv_chat(body, query):
    return {"messages": diplomacy.advisor_chat(q(query, "role", ""))}


@route("POST", "/api/advisors/send")
def api_adv_send(body, query):
    return {"messages": diplomacy.advisor_send(body.get("role"), body.get("text")), "hud": G.hud()}


# ---- армия ----
@route("GET", "/api/army")
def api_army(body, query):
    return army.view()


@route("POST", "/api/army/act")
def api_army_act(body, query):
    msg = army.act(body.get("kind"), body.get("cat"), body.get("idx"), body.get("name"), body.get("value"))
    return {"message": msg, "army": army.view()}


@route("POST", "/api/army/project")
def api_army_project(body, query):
    msg = army.project_act(body.get("kind"), body.get("idx"), body.get("value"))
    return {"message": msg, "army": army.view()}


@route("GET", "/api/army/intel")
def api_army_intel(body, query):
    return army.intel(q(query, "country") or (army.intel_targets() or [""])[0])


@route("POST", "/api/army/audit")
def api_army_audit(body, query):
    msg = army.audit(body.get("country") or None)
    return {"message": msg, "army": army.view()}


# ---- саммиты ----
@route("GET", "/api/summit")
def api_summit(body, query):
    return summit.state()


def _summit_action(fn):
    def handler(body, query):
        fn(body)
        return summit.state()
    return handler


for _name, _fn in {
    "create": lambda b: summit.create(b.get("title"), b.get("topic"), b.get("participants"), b.get("secrecy")),
    "speak": lambda b: summit.speak(b.get("text")), "propose": lambda b: summit.propose(b.get("text")),
    "vote": lambda b: summit.vote(b.get("vote")), "walkout": lambda b: summit.walkout(),
    "advice": lambda b: summit.advice(), "close": lambda b: summit.close(),
}.items():
    ROUTES[("POST", f"/api/summit/{_name}")] = _summit_action(_fn)


@route("GET", "/api/ui")
def api_ui(body, query):
    return {"prefs": uiprefs.load(), "categories": uiprefs.CATEGORIES,
            "fonts": {"bundled": uiprefs.BUNDLED, "user": uiprefs.user_fonts()}}


@route("POST", "/api/ui")
def api_ui_set(body, query):
    return {"prefs": uiprefs.update(body)}


@route("POST", "/api/fonts/upload")
def api_font_upload(body, query):
    try:
        name = uiprefs.save_user_font(body.get("name"), body.get("raw"))
    except ValueError as e:
        raise G.GameError(str(e))
    return {"file": name, "fonts": uiprefs.user_fonts()}


@route("POST", "/api/fonts/delete")
def api_font_delete(body, query):
    try:
        uiprefs.delete_user_font(body.get("file"))
    except ValueError as e:
        raise G.GameError(str(e))
    return {"fonts": uiprefs.user_fonts(), "prefs": uiprefs.load()}


# Пока идёт ход, остальное состояние менять/читать нельзя: агенты работают с живым миром.
ALWAYS_OK = {"/api/turn/status", "/api/state", "/api/config", "/api/menu", "/api/ui"}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    server_version = "GeoTable/1.0"

    def log_message(self, fmt, *args):      # тишина в консоли
        pass

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").lower()
        return host in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def _send(self, code, payload, ctype="application/json; charset=utf-8", extra=None):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _static(self, path):
        base, rel = WEB_DIR, None
        if path in ("/", ""):
            rel = "index.html"
        elif path.startswith("/web/"):
            rel = path[len("/web/"):]
        elif path.startswith("/fonts/"):                 # шрифты, загруженные игроком
            base, rel = uiprefs.USER_FONTS_DIR, unquote(path[len("/fonts/"):])
        full = os.path.normpath(os.path.join(base, rel)) if rel else None
        if not full or not full.startswith(os.path.normpath(base) + os.sep) or not os.path.isfile(full):
            return self._send(404, {"error": "Не найдено"})
        ctype = FONT_MIME.get(os.path.splitext(full)[1].lower()) or mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def _api(self, method, parsed):
        if not self._host_ok():
            return self._send(403, {"error": "Недопустимый Host"})
        if method == "POST" and self.headers.get(CSRF_HEADER[0]) != CSRF_HEADER[1]:
            return self._send(403, {"error": "Нет заголовка защиты"})
        fn = ROUTES.get((method, parsed.path))
        if not fn:
            return self._send(404, {"error": "Нет такого метода API"})
        body = {}
        if method == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, {"error": "Слишком большой запрос"})
            raw = self.rfile.read(n) if n else b""
            if parsed.path in RAW_ROUTES:
                body = {"raw": raw, "name": unquote(self.headers.get("X-File-Name", ""))}
            else:
                try:
                    body = json.loads(raw.decode("utf-8")) if raw else {}
                except ValueError:
                    return self._send(400, {"error": "Некорректный JSON"})
        if G.TURN.running and parsed.path not in ALWAYS_OK and not parsed.path.startswith("/api/turn"):
            return self._send(409, {"error": "Идёт обработка хода — подождите"})
        try:
            with LOCK:
                result = fn(body if isinstance(body, dict) else {}, parse_qs(parsed.query))
        except G.GameError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        if isinstance(result, Raw):
            ascii_name = "".join(ch if ord(ch) < 128 else "_" for ch in result.filename)
            return self._send(200, result.data, f"{result.content_type}; charset=utf-8",
                              {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; "
                                                      f"filename*=UTF-8''{quote(result.filename)}"})
        self._send(200, result)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            return self._api("GET", parsed)
        if not self._host_ok():
            return self._send(403, {"error": "Недопустимый Host"})
        self._static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            return self._api("POST", parsed)
        self._send(404, {"error": "Не найдено"})


def create_server(port=DEFAULT_PORT):
    last = None
    for p in range(port, port + 11):        # если порт занят — берём следующий
        try:
            return ThreadingHTTPServer(("127.0.0.1", p), Handler)
        except OSError as e:
            last = e
    raise last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    server = create_server(args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Geopolitics AI: {url}\nЗакройте это окно, чтобы остановить игру.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
