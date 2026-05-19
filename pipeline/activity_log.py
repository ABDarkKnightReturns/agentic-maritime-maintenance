"""
Activity Log — module-level singleton that survives Streamlit re-runs.

Streamlit re-executes app.py top-to-bottom on every interaction, which
recreates any module-level deque defined there. By moving the deque here
(a separately imported module), Python's import cache ensures it is only
initialised once per process, so background threads and the UI always
share the same object.
"""
from collections import deque
from datetime import datetime, timezone
import threading

_log: deque = deque(maxlen=15)
_lock = threading.Lock()

# Thread-safe flag for auto-watchkeeper toggle.
# Using threading.Event avoids calling st.session_state from a background
# thread, which raises RuntimeError: "No active script run context".
auto_watchkeeper_enabled = threading.Event()
auto_watchkeeper_enabled.set()  # ON by default


def log_activity(icon: str, agent: str, asset: str, message: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    with _lock:
        _log.appendleft({"ts": ts, "icon": icon, "agent": agent,
                          "asset": asset, "message": message})


def get_log() -> list[dict]:
    with _lock:
        return list(_log)


def clear_log():
    with _lock:
        _log.clear()
