"""
SQLite database initialisation.
All three stores share one DB file. Each store owns its own table(s).
WAL mode is enabled so the UI (reader) and background writers don't block each other.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "maritime_demo.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA wal_autocheckpoint=100")  # checkpoint every 100 pages, not 1000
    conn.row_factory = sqlite3.Row
    return conn


def initialise_schema():
    conn = get_connection()
    cur = conn.cursor()

    # --- Raw + Derived telemetry ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id    TEXT    NOT NULL,
            ts          TEXT    NOT NULL,
            tag         TEXT    NOT NULL,
            value       REAL    NOT NULL,
            category    TEXT    NOT NULL DEFAULT 'Raw'
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_asset_tag_ts
        ON telemetry (asset_id, tag, ts DESC)
    """)

    # --- Derived health snapshots (full JSON per asset per second) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS derived_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id    TEXT    NOT NULL,
            ts          TEXT    NOT NULL,
            snapshot    TEXT    NOT NULL
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_derived_asset_ts
        ON derived_snapshots (asset_id, ts DESC)
    """)

    # --- Alert events ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id            TEXT PRIMARY KEY,
            asset_id            TEXT NOT NULL,
            ts                  TEXT NOT NULL,
            event_type          TEXT NOT NULL,
            severity            TEXT NOT NULL,
            title               TEXT NOT NULL,
            description         TEXT,
            agent_name          TEXT,
            agent_reasoning     TEXT,
            recommended_action  TEXT,
            acknowledged        INTEGER DEFAULT 0,
            acknowledged_by     TEXT,
            acknowledged_at     TEXT,
            resolved            INTEGER DEFAULT 0,
            resolved_at         TEXT,
            work_order_id       TEXT
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_asset_ts
        ON events (asset_id, ts DESC)
    """)

    # --- Work orders ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS work_orders (
            work_order_id   TEXT PRIMARY KEY,
            asset_id        TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            status          TEXT NOT NULL,
            priority        INTEGER NOT NULL,
            title           TEXT NOT NULL,
            payload         TEXT NOT NULL    -- full WorkOrder JSON
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_wo_asset_status
        ON work_orders (asset_id, status)
    """)

    conn.commit()
    conn.close()
