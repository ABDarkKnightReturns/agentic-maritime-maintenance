"""
High-Frequency Data Store — circular buffer per asset per tag.

Each asset emits 12 HF tags at 10 Hz.
We keep 10 minutes of rolling history (6000 samples per tag).
Thread-safe. On alarm, capture_alarm_snapshot() freezes a 60-second
window for ML analysis; get_alarm_snapshot() returns it as a DataFrame.
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

# ── Constants ─────────────────────────────────────────────────────────────────

HF_RATE        = 10          # Hz
HF_WINDOW_S    = 600         # seconds kept in rolling buffer (10 min)
HF_MAXLEN      = HF_RATE * HF_WINDOW_S   # 6000 samples
HF_SNAPSHOT_S  = 60          # seconds frozen on alarm trigger


# ── HFSample — one tick of all HF tags for one asset ─────────────────────────

@dataclass
class HFSample:
    asset_id:  str
    timestamp: datetime
    readings:  dict[str, float]   # 12 tags at this instant


# ── HFSnapshot — frozen window captured on alarm ──────────────────────────────

@dataclass
class HFSnapshot:
    asset_id:      str
    captured_at:   datetime
    duration_s:    float
    timestamps:    list[datetime]
    data:          dict[str, list[float]]   # tag → value list (aligned with timestamps)

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(self.data, index=self.timestamps)
        df.index.name = "timestamp"
        return df


# ── HFStore ───────────────────────────────────────────────────────────────────

class HFStore:
    """
    Circular buffer of HF samples.  One deque per (asset_id, tag).
    Thread-safe for concurrent writes from the HF sim loop and reads
    from the ML pipeline.
    """

    def __init__(self):
        # _buffers[asset_id][tag] = deque of (timestamp, value) pairs
        self._buffers: dict[str, dict[str, deque]] = {}
        self._lock    = threading.Lock()
        # Frozen snapshots captured at alarm time
        self._alarm_snapshots: dict[str, HFSnapshot] = {}
        self._sample_counts: dict[str, int] = {}

    # ── Write ──────────────────────────────────────────────────────────────

    def update(self, sample: HFSample) -> None:
        """Store one HF sample (all tags) for an asset."""
        with self._lock:
            if sample.asset_id not in self._buffers:
                self._buffers[sample.asset_id] = {}
                self._sample_counts[sample.asset_id] = 0
            buf = self._buffers[sample.asset_id]
            for tag, value in sample.readings.items():
                if tag not in buf:
                    buf[tag] = deque(maxlen=HF_MAXLEN)
                buf[tag].append((sample.timestamp, value))
            self._sample_counts[sample.asset_id] += 1

    # ── Read window ────────────────────────────────────────────────────────

    def get_window(self, asset_id: str, duration_s: float = 120) -> Optional[pd.DataFrame]:
        """
        Return the most recent `duration_s` seconds of HF data as a DataFrame.
        Columns = tag names, index = timestamps.
        Returns None if the asset has no buffered data.
        """
        with self._lock:
            buf = self._buffers.get(asset_id)
            if not buf:
                return None
            n_samples = int(duration_s * HF_RATE)
            data: dict[str, list] = {}
            timestamps: Optional[list] = None

            for tag, dq in buf.items():
                window = list(dq)[-n_samples:]
                if not window:
                    continue
                if timestamps is None:
                    timestamps = [t for t, _ in window]
                data[tag] = [v for _, v in window]

            if not data or timestamps is None:
                return None

            # Align all series to the minimum length (tags may differ by ±1 sample)
            min_len = min(len(v) for v in data.values())
            aligned_ts = timestamps[-min_len:]
            aligned_data = {tag: vals[-min_len:] for tag, vals in data.items()}
            df = pd.DataFrame(aligned_data, index=aligned_ts)
            df.index.name = "timestamp"
            return df

    # ── Alarm snapshot ─────────────────────────────────────────────────────

    def capture_alarm_snapshot(self, asset_id: str, duration_s: float = HF_SNAPSHOT_S) -> None:
        """
        Freeze the last `duration_s` seconds of HF data for this asset.
        Called by AlarmManager when a watchkeeper trigger is queued.
        Subsequent calls overwrite the previous snapshot (one per asset).
        """
        with self._lock:
            buf = self._buffers.get(asset_id)
            if not buf:
                return
            n_samples = int(duration_s * HF_RATE)
            data: dict[str, list[float]] = {}
            timestamps: Optional[list[datetime]] = None

            for tag, dq in buf.items():
                window = list(dq)[-n_samples:]
                if not window:
                    continue
                if timestamps is None:
                    timestamps = [t for t, _ in window]
                data[tag] = [v for _, v in window]

            if not data or timestamps is None:
                return

            min_len = min(len(v) for v in data.values())
            aligned_ts = timestamps[-min_len:]
            aligned_data = {tag: vals[-min_len:] for tag, vals in data.items()}
            actual_duration = len(aligned_ts) / HF_RATE

            self._alarm_snapshots[asset_id] = HFSnapshot(
                asset_id=asset_id,
                captured_at=datetime.now(timezone.utc),
                duration_s=actual_duration,
                timestamps=list(aligned_ts),
                data=aligned_data,
            )

    def get_alarm_snapshot(self, asset_id: str) -> Optional[pd.DataFrame]:
        """Return the frozen alarm snapshot as a DataFrame, or None."""
        with self._lock:
            snap = self._alarm_snapshots.get(asset_id)
            if snap is None:
                return None
            return snap.to_dataframe()

    def has_alarm_snapshot(self, asset_id: str) -> bool:
        with self._lock:
            return asset_id in self._alarm_snapshots

    # ── Status ─────────────────────────────────────────────────────────────

    def get_buffer_status(self) -> dict[str, dict]:
        """Return sample count and age info per asset (for UI status indicator)."""
        with self._lock:
            status = {}
            for asset_id, count in self._sample_counts.items():
                buf = self._buffers.get(asset_id, {})
                # Get most recent timestamp from first available tag
                latest_ts = None
                tag_count = 0
                for tag, dq in buf.items():
                    if dq:
                        ts, _ = dq[-1]
                        latest_ts = ts
                        tag_count += 1
                        break

                # Approximate buffered seconds
                buffered_s = min(count / HF_RATE, HF_WINDOW_S) if count > 0 else 0

                status[asset_id] = {
                    "total_samples":   count,
                    "buffered_s":      round(buffered_s, 1),
                    "tag_count":       tag_count,
                    "has_snapshot":    asset_id in self._alarm_snapshots,
                    "latest_ts":       latest_ts.isoformat() if latest_ts else None,
                }
            return status

    def clear(self, asset_id: Optional[str] = None) -> None:
        """Clear buffers and snapshots for one asset or all assets."""
        with self._lock:
            if asset_id:
                self._buffers.pop(asset_id, None)
                self._alarm_snapshots.pop(asset_id, None)
                self._sample_counts.pop(asset_id, None)
            else:
                self._buffers.clear()
                self._alarm_snapshots.clear()
                self._sample_counts.clear()


# Module-level singleton — import this everywhere
hf_store = HFStore()
