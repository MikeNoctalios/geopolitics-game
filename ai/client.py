"""Клиент LLM: конфиг, устойчивый вызов API и разбор JSON-ответов."""
import json
import os
import re
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "",
    "model_name": "gpt-4o-mini",
    "theme": "Светлая",   # зарезервировано под будущий UI
    "max_workers": 4,     # параллельных запросов за ход; 1 = строго по очереди
    "json_mode": False,   # true = просить у API строгий JSON (response_format); часть прокси от этого отвечает 500
}
REQUEST_TIMEOUT = 120.0   # прежние 45 с обрывали длинные JSON-ответы
JSON_NUDGE = "Выполни задачу. Ответ — только валидный JSON, без пояснений."


# --------------------------------------------------------------------------- #
# Конфиг
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if v is not None})
    except (OSError, ValueError):
        pass
    for k in ("api_key", "base_url", "model_name"):
        cfg[k] = str(cfg.get(k) or "").strip()
    cfg["model_name"] = cfg["model_name"] or DEFAULT_CONFIG["model_name"]
    try:
        cfg["max_workers"] = max(1, min(8, int(cfg["max_workers"])))
    except (TypeError, ValueError):
        cfg["max_workers"] = DEFAULT_CONFIG["max_workers"]
    cfg["json_mode"] = cfg.get("json_mode") is True
    return cfg


def save_config(api_key, base_url, model_name, theme=""):
    cfg = load_config()  # сохраняем и прочие ключи (например, max_workers)
    cfg.update({
        "api_key": str(api_key or "").strip(),   # пробел/перенос из буфера = 401
        "base_url": str(base_url or "").strip(),
        "model_name": str(model_name or "").strip() or DEFAULT_CONFIG["model_name"],
        "theme": theme or cfg.get("theme", ""),
    })
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(tmp, 0o600)   # в файле лежит ключ
    except OSError:
        pass
    os.replace(tmp, CONFIG_FILE)


def get_ai_client(api_key, base_url):
    from openai import OpenAI  # ленивый импорт: модуль нужен только при реальных вызовах
    kwargs = {
        "api_key": api_key or "dummy-key",
        "timeout": REQUEST_TIMEOUT,
        "max_retries": 0,      # ретраи делаем сами (иначе 2×3 попыток × таймаут)
    }
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def estimate_tokens(text: str) -> int:
    return max(1, len(str(text)) // 3)


# --------------------------------------------------------------------------- #
# Разбор JSON из ответа модели
# --------------------------------------------------------------------------- #
def _close_json(s: str) -> str:
    """Дописывает недостающие кавычку и скобки у оборванного JSON."""
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    return s + ('"' if in_str else "") + "".join(reversed(stack))


def _repair_truncated(text: str):
    """Ответ оборвался по лимиту токенов: отрезаем хвост до валидного состояния."""
    start = text.find("{")
    if start < 0:
        return None
    cand = text[start:]
    for _ in range(80):
        try:
            obj = json.loads(_close_json(cand.rstrip().rstrip(",")))
            return obj if isinstance(obj, dict) else None
        except ValueError:
            cut = cand.rfind(",")
            if cut <= 0:
                return None
            cand = cand[:cut]
    return None


def clean_json_response(raw_text):
    """Возвращает dict из ответа модели или None, если разобрать не удалось."""
    if not raw_text:
        return None
    text = re.sub(r"<think>.*?</think>", "", str(raw_text), flags=re.S | re.I).strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except ValueError:
        pass

    decoder = json.JSONDecoder()
    for m in list(re.finditer(r"\{", text))[:20]:       # первый корректный {...} в тексте
        chunk = text[m.start():]
        try:
            obj, _ = decoder.raw_decode(chunk)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        try:
            obj = json.loads(re.sub(r",\s*([\]}])", r"\1", chunk))  # висячие запятые
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        fixed = _repair_truncated(chunk)                 # оборван по лимиту токенов
        if fixed is not None:
            return fixed
    return None


# --------------------------------------------------------------------------- #
# Вызовы API
# --------------------------------------------------------------------------- #
def _rejected_param(err, kwargs):
    """Провайдер отверг необязательный параметр (response_format/temperature)?"""
    status = getattr(err, "status_code", None)
    if status not in (None, 400, 422):
        return None
    msg = str(err).lower()
    for p in ("response_format", "temperature"):
        if p in kwargs and (p in msg or (p == "response_format" and "json" in msg)):
            return p
    return None


def _create(client, **kwargs):
    """chat.completions.create, который сам отказывается от параметров, не поддерживаемых провайдером."""
    dropped = getattr(client, "_dropped_params", None)
    if dropped is None:
        dropped = set()
        try:
            client._dropped_params = dropped
        except Exception:
            pass
    for p in dropped:
        kwargs.pop(p, None)
    for _ in range(3):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            p = _rejected_param(e, kwargs)
            if not p:
                raise
            kwargs.pop(p, None)
            dropped.add(p)
    return client.chat.completions.create(**kwargs)


def _usage_tokens(resp, messages, raw):
    try:
        n = int(resp.usage.total_tokens)
        if n > 0:
            return n
    except Exception:
        pass
    return estimate_tokens(str(messages) + raw)


def _is_fatal(err) -> bool:
    """Повтор не поможет: неверный ключ, модель, доступ или слишком длинный запрос."""
    return getattr(err, "status_code", None) in (400, 401, 403, 404, 422)


def _status(err):
    code = getattr(err, "status_code", None)
    return code if isinstance(code, int) else None


def _pause(err, attempt):
    code = _status(err)
    time.sleep((5 if code == 429 else 3 if code and code >= 500 else 1.5) * attempt)


def _log_failure(kind, model, messages, err, json_mode, started=None):
    """Дописывает сбой в logs/api_errors.log (без ключа): по нему видно, на каких запросах ломается провайдер."""
    try:
        d = os.path.join(BASE_DIR, "logs")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "api_errors.log")
        if os.path.exists(path) and os.path.getsize(path) > 1_000_000:
            os.replace(path, path + ".old")
        head = str(messages[0].get("content", "")).strip().replace("\n", " ")[:70] if messages else ""
        size = sum(len(str(m.get("content", ""))) for m in messages)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {kind} | model={model} | json_mode={json_mode} | "
                    f"prompt_chars={size} | http={_status(err)} | after={time.time() - started:.0f}s | {head} | {str(err)[:300]}\n")
    except OSError:
        pass


def safe_chat_completion(client, model: str, messages: list, temperature: float = 0.3,
                         max_attempts: int = 3, fallback_dict: dict = None, json_mode: bool = None) -> tuple:
    """(dict, tokens). При окончательном сбое возвращает fallback_dict (или {}) + ключ '_error'.

    json_mode=None -> берётся из config.json (по умолчанию выключен). Если сервер отвечает 5xx
    именно на запрос с response_format, следующие попытки идут уже без него."""
    use_json = (load_config().get("json_mode") is True) if json_mode is None else json_mode
    started_with_json, started = use_json, time.time()
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            kwargs = {"model": model, "messages": messages, "temperature": temperature}
            if use_json:
                kwargs["response_format"] = {"type": "json_object"}
            resp = _create(client, **kwargs)
            choice = resp.choices[0]
            raw = choice.message.content or ""
            parsed = clean_json_response(raw)
            if parsed is not None:
                return parsed, _usage_tokens(resp, messages, raw)
            cut = getattr(choice, "finish_reason", "") == "length"
            last_err = ValueError("ответ модели оборван по лимиту токенов" if cut
                                  else "модель вернула не-JSON")
        except Exception as e:
            last_err = e
            if _is_fatal(e):
                break
            if use_json and (_status(e) or 0) >= 500:
                use_json = False          # прокси мог споткнуться о response_format — пробуем «как раньше»
        if attempt < max_attempts:
            _pause(last_err, attempt)
    _log_failure("json", model, messages, last_err, started_with_json, started)
    res = dict(fallback_dict or {})
    res["_error"] = f"{type(last_err).__name__}: {last_err}"
    return res, 0


def call_json(client, model, prompt: str, temperature: float = 0.5,
              fallback: dict = None, max_attempts: int = 3, json_mode: bool = None) -> tuple:
    """Агент отдаёт промпт как system, плюс короткий user (часть провайдеров падает без user-сообщения)."""
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": JSON_NUDGE}]
    return safe_chat_completion(client, model, messages, temperature, max_attempts, fallback, json_mode)


def chat_text(client, model, messages: list, temperature: float = 0.7, max_attempts: int = 2) -> tuple:
    """(текст | None, tokens, ошибка | None) — для обычных чатов (советники, МИД)."""
    last_err, started = None, time.time()
    for attempt in range(1, max_attempts + 1):
        try:
            resp = _create(client, model=model, messages=messages, temperature=temperature)
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text, _usage_tokens(resp, messages, text), None
            last_err = ValueError("пустой ответ модели")
        except Exception as e:
            last_err = e
            if _is_fatal(e):
                break
        if attempt < max_attempts:
            _pause(last_err, attempt)
    _log_failure("text", model, messages, last_err, False, started)
    return None, 0, f"{type(last_err).__name__}: {last_err}"


def test_connection(cfg: dict) -> tuple:
    """(ok, сообщение) — проверка ключа, URL и имени модели из настроек."""
    if not cfg.get("api_key"):
        return False, "API-ключ не указан."
    try:
        cl = get_ai_client(cfg["api_key"], cfg.get("base_url", ""))
    except Exception as e:
        return False, f"Не удалось создать клиент: {e}"
    text, _, err = chat_text(cl, cfg["model_name"],
                             [{"role": "user", "content": "Ответь одним словом: ок"}],
                             temperature=0, max_attempts=1)
    return (True, f"Связь есть. Ответ модели: «{text[:60]}»") if text else (False, err)
