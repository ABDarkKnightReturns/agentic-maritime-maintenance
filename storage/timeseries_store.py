"""
Timeseries Store
-----------------
Subscribes to Raw telemetry and Derived snapshots on the UNS broker,
persists them to SQLite, and exposes query methods for the UI.

Retention: keeps last MAX_ROWS_PER_TAG rows per asset/tag combination.
At 1 Hz that's ~10 minutes of live history — enough for trend charts.
"""
import json
import threading
import time
from datetime import datetime, timezone
from queue import Empty

from models.uns import UNSMessage, UNSCategory
from pipeline.uns_broker import broker
from storage.database import get_connection, initialise_schema
from loguru import logger

MAX_ROWS_PER_TAG = 600   # 10 minutes at 1 Hz
PRUNE_EVERY_N = 300      # prune old rows every 300 inserts


class TimeseriesStore:

    def __init__(self):
        initialise_schema()
        self._conn = get_connection()
        self._lock = threading.Lock()
        self._insert_count = 0
        self._running = False
        self._thread: threading.Thread | None = None

        # Subscribe to raw sensor readings
        self._raw_q = broker.subscribe(
            "Maersk/+/EngineRoom/+/+/Raw/#",
            subscriber_id="ts_store_raw",
        )
        # Subscribe to derived snapshots
        self._derived_q = broker.subscribe(
            "Maersk/+/EngineRoom/+/+/Derived/#",
            subscriber_id="ts_store_derived",
        )

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="ts_store")
        self._thread.start()
        logger.info("[TSStore] Started")

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------
    # Writer loop
    # ------------------------------------------------------------------

    def _run(self):
        while self._running:
            batch_raw = []
            batch_derived = []

            # Drain raw queue
            for _ in range(200):
                try:
                    msg: UNSMessage = self._raw_q.get_nowait()
                    if msg.tag and isinstance(msg.value, (int, float)):
                        batch_raw.append((
                            msg.asset_id,
                            msg.timestamp.isoformat(),
                            msg.tag,
                            float(msg.value),
                            "Raw",
                        ))
                except Empty:
                    break

            # Drain derived queue
            for _ in range(50):
                try:
                    msg: UNSMessage = self._derived_q.get_nowait()
                    if isinstance(msg.value, dict):
                        batch_derived.append((
                            msg.asset_id,
                            msg.timestamp.isoformat(),
                            json.dumps(msg.value),
                        ))
                except Empty:
                    break

            if batch_raw or batch_derived:
                with self._lock:
                    cur = self._conn.cursor()
                    if batch_raw:
                        cur.executemany(
                            "INSERT INTO telemetry (asset_id, ts, tag, value, category) VALUES (?,?,?,?,?)",
                            batch_raw,
                        )
                        self._insert_count += len(batch_raw)
                    if batch_derived:
                        cur.executemany(
                            "INSERT INTO derived_snapshots (asset_id, ts, snapshot) VALUES (?,?,?)",
                            batch_derived,
                        )
                    self._conn.commit()

                    # Periodic pruning + WAL checkpoint to keep WAL file small
                    prev = self._insert_count - len(batch_raw)
                    if (prev // PRUNE_EVERY_N) < (self._insert_count // PRUNE_EVERY_N):
                        self._prune(cur)
                        self._conn.commit()
                        # TRUNCATE forces WAL back into the main db file
                        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            time.sleep(0.2)

    def _prune(self, cur):
        """Keep only the most recent MAX_ROWS_PER_TAG rows per asset/tag."""
        cur.execute("""
            DELETE FROM telemetry WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY asset_id, tag ORDER BY ts DESC
                    ) AS rn FROM telemetry
                ) WHERE rn <= ?
            )
        """, (MAX_ROWS_PER_TAG,))

        cur.execute("""
            DELETE FROM derived_snapshots WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY asset_id ORDER BY ts DESC
                    ) AS rn FROM derived_snapshots
                ) WHERE rn <= 120
            )
        """)

    # ------------------------------------------------------------------
    # Read API (used by UI)
    # ------------------------------------------------------------------

    def get_tag_history(
        self, asset_id: str, tag: str, limit: int = 120
    ) -> list[dict]:
        """Returns [{ts, value}] newest-first for sparkline / trend charts."""
        with self._lock:
            cur = self._conn.execute(
                """SELECT ts, value FROM telemetry
                   WHERE asset_id=? AND tag=?
                   ORDER BY ts DESC LIMIT ?""",
                (asset_id, tag, limit),
            )
            rows = cur.fetchall()
        return [{"ts": r["ts"], "value": r["value"]} for r in reversed(rows)]

    def get_latest_readings(self, asset_id: str) -> dict[str, float]:
        """Returns {tag: latest_value} for the asset's current state card."""
        with self._lock:
            cur = self._conn.execute(
                """SELECT tag, value FROM telemetry
                   WHERE asset_id=? AND ts = (
                       SELECT MAX(ts) FROM telemetry WHERE asset_id=? AND tag=telemetry.tag
                   )
                   GROUP BY tag""",
                (asset_id, asset_id),
            )
            rows = cur.fetchall()
        return {r["tag"]: r["value"] for r in rows}

    def get_latest_derived(self, asset_id: str) -> dict | None:
        """Returns the most recent derived snapshot dict for an asset."""
        with self._lock:
            cur = self._conn.execute(
                """SELECT snapshot FROM derived_snapshots
                   WHERE asset_id=? ORDER BY ts DESC LIMIT 1""",
                (asset_id,),
            )
            row = cur.fetchone()
        return json.loads(row["snapshot"]) if row else None

    def clear_all(self):
        """Delete all telemetry and derived snapshot rows — called on fleet reset."""
        with self._lock:
            self._conn.execute("DELETE FROM telemetry")
            self._conn.execute("DELETE FROM derived_snapshots")
            self._conn.commit()
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        logger.info("[TSStore] All timeseries data cleared on fleet reset")

    def get_derived_history(self, asset_id: str, limit: int = 60) -> list[dict]:
        """Returns [{ts, health_score, rul_days, vibration_rms}] for trend panel."""
        with self._lock:
            cur = self._conn.execute(
                """SELECT ts, snapshot FROM derived_snapshots
                   WHERE asset_id=? ORDER BY ts DESC LIMIT ?""",
                (asset_id, limit),
            )
            rows = cur.fetchall()
        result = []
        for r in reversed(rows):
            snap = json.loads(r["snapshot"])
            result.append({
                "ts": r["ts"],
                "health_score": snap.get("overall_health_score"),
                "rul_days": snap.get("rul_days"),
                "vibration_rms": snap.get("vibration_rms_mms"),
                "anomaly_score": snap.get("anomaly_score"),
            })
        return result
