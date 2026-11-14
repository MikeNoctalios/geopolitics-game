"""Подставной модуль `streamlit` для запуска ядра без Streamlit (веб-интерфейс «стол», server.py).

Ядро хранит игру в st.session_state и иногда зовёт st.spinner/st.status/st.write. Здесь session_state —
обычный глобальный словарь с доступом через точку, а остальное — безвредные заглушки.
"""
import contextlib
import sys
import types


class RerunException(BaseException):
    pass


class SessionState(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v

    def __delattr__(self, k):
        del self[k]


class _Status:
    def update(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def install():
    st = sys.modules.get("streamlit")
    if st is not None and getattr(st, "_headless", False):
        return st
    st = types.ModuleType("streamlit")
    st._headless = True
    st.session_state = SessionState()
    st.messages = []

    def note(kind):
        return lambda *a, **k: st.messages.append((kind, str(a[0]) if a else "")) or None

    for kind in ("write", "info", "warning", "error", "success", "caption", "markdown", "toast", "code"):
        setattr(st, kind, note(kind))
    st.spinner = lambda *a, **k: contextlib.nullcontext()
    st.status = lambda *a, **k: _Status()
    st.expander = lambda *a, **k: contextlib.nullcontext()

    def rerun():
        raise RerunException()

    st.rerun = rerun
    sys.modules["streamlit"] = st
    return st
