"""
Event Store
------------
Persists AlertEvent objects raised by the 5 agents.
Provides query methods for the UI event feed and agent context retrieval.
"""
import json
import threading
from datetime import datetime
from typing import Optional

from models.events import AlertEvent, AlertSeverity
from storage.database import get_connection, initialise_schema
from loguru import logger


class EventStore:

    def __init__(self):
        initialise_schema()
        self._conn = get_connection()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_event(self, event: AlertEvent):
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO events
                   (event_id, asset_id, ts, event_type, severity, title,
                    description, agent_name, agent_reasoning, recommended_action,
                    acknowledged, acknowledged_by, acknowledged_at,
                    resolved, resolved_at, work_order_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.event_id,
                    event.asset_id,
                    event.timestamp.isoformat(),
                    event.event_type.value,
                    event.severity.value,
                    event.title,
                    event.description,
                    event.agent_name,
                    event.agent_reasoning,
                    event.recommended_action,
                    int(event.acknowledged),
                    event.acknowledged_by,
                    event.acknowledged_at.isoformat() if event.acknowledged_at else None,
                    int(event.resolved),
                    event.resolved_at.isoformat() if event.resolved_at else None,
                    event.work_order_id,
                ),
            )
            self._conn.commit()

    def acknowledge_event(self, event_id: str, acknowledged_by: str):
        now = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                """UPDATE events
                   SET acknowledged=1, acknowledged_by=?, acknowledged_at=?
                   WHERE event_id=?""",
                (acknowledged_by, now, event_id),
            )
            self._conn.commit()

    def resolve_event(self, event_id: str):
        now = datetime.utcnow().isoformat()
        with self._lock:
            self._conn.execute(
                "UPDATE events SET resolved=1, resolved_at=? WHERE event_id=?",
                (now, event_id),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_active_events(
        self, asset_id: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """Unresolved events, newest first. Used by UI event feed."""
        query = "SELECT * FROM events WHERE resolved=0"
        params: list = []
        if asset_id:
            query += " AND asset_id=?"
            params.append(asset_id)
        query += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            cur = self._conn.execute(query, params)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_all_events(
        self, asset_id: Optional[str] = None, limit: int = 100
    ) -> list[dict]:
        query = "SELECT * FROM events"
        params: list = []
        if asset_id:
            query += " WHERE asset_id=?"
            params.append(asset_id)
        query += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            cur = self._conn.execute(query, params)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_event_count_by_severity(self, asset_id: Optional[str] = None) -> dict:
        query = """SELECT severity, COUNT(*) as cnt FROM events WHERE resolved=0"""
        params: list = []
        if asset_id:
            query += " AND asset_id=?"
            params.append(asset_id)
        query += " GROUP BY severity"
        with self._lock:
            cur = self._conn.execute(query, params)
            rows = cur.fetchall()
        return {r["severity"]: r["cnt"] for r in rows}

    def clear_all(self):
        """Delete all event rows — called on fleet reset."""
        with self._lock:
            self._conn.execute("DELETE FROM events")
            self._conn.commit()
        logger.info("[EventStore] All events cleared on fleet reset")

    def get_context_for_agent(self, asset_id: str, n: int = 5) -> list[dict]:
        """Last N events for an asset — injected into agent context."""
        with self._lock:
            cur = self._conn.execute(
                """SELECT ts, severity, title, description, agent_reasoning
                   FROM events WHERE asset_id=?
                   ORDER BY ts DESC LIMIT ?""",
                (asset_id, n),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
