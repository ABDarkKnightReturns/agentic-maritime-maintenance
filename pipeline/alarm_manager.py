"""
Alarm Manager — ISA-18.2-style alarm lifecycle.

Sits between the CEP engine and the Watchkeeper agent.

Lifecycle:
  INACTIVE  → value within limits (no alarm)
  ACTIVE    → threshold breached; Watchkeeper trigger queued
  RESOLVED  → value returned to normal (auto-cleared)

Rules:
  - An alarm cannot be dismissed while the breach condition persists.
  - Watchkeeper fires ONCE per fault event per asset.
    After firing, the asset is marked as "under investigation" and all
    further auto-triggers are suppressed until reset_asset() is called
    (i.e. the operator presses the Reset button for that asset / fleet).
  - Each alarm carries the metric name, breach value, threshold, and source.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Queue
from typing import Optional

from data.thresholds import get_thresholds, Threshold
from models.derived import DerivedMetrics
from loguru import logger


@dataclass
class ActiveAlarm:
    asset_id:        str
    metric:          str
    level:           str          # "Warning" or "Alarm"
    value:           float
    threshold:       float
    unit:            str
    source:          str
    triggered_at:    datetime
    last_value:      float = field(default=0.0)
    acknowledged:    bool  = False
    tier:            int   = 2    # 2=Investigate, 3=Critical/SOLAS
    compliance_code: Optional[str] = None  # e.g. "SOLAS-II-1/28"

    @property
    def age_minutes(self) -> float:
        return (datetime.now(timezone.utc) - self.triggered_at).total_seconds() / 60


class AlarmManager:
    """
    Singleton-style — one instance shared between CEP and app.
    Thread-safe.
    """

    def __init__(self):
        self._lock  = threading.Lock()
        # (asset_id, metric) → ActiveAlarm
        self._active: dict[tuple, ActiveAlarm] = {}
        # Assets that have already had a Watchkeeper triggered this fault cycle.
        # Cleared only when reset_asset() / clear_all() is called (fleet reset).
        # This ensures one Watchkeeper per fault event — no stacking chains.
        self._agent_fired: set[str] = set()
        # Queue the app drains to run Watchkeeper
        self.trigger_queue: Queue[dict] = Queue()
        # Queue for suppressed triggers — app can surface these in the Activity Feed
        self.suppressed_queue: Queue[dict] = Queue()

    # ── Called by CEP after every compute cycle ───────────────────────────────

    def evaluate(self, metrics: DerivedMetrics):
        """Check all thresholds for this asset. Fire/resolve alarms as needed."""
        asset_id   = metrics.asset_id
        thresholds = get_thresholds(asset_id)
        if not thresholds:
            return

        with self._lock:
            for metric_name, threshold in thresholds.items():
                value = getattr(metrics, metric_name, None)
                if value is None:
                    continue

                key   = (asset_id, metric_name)
                level = threshold.check(value)

                if level:
                    self._handle_breach(key, asset_id, metric_name,
                                        level, value, threshold)
                else:
                    self._handle_resolved(key, asset_id, metric_name, value)

    def _handle_breach(self, key: tuple, asset_id: str, metric: str,
                       level: str, value: float, threshold: Threshold):
        existing = self._active.get(key)

        if existing is None:
            # New breach — create alarm
            alarm = ActiveAlarm(
                asset_id=asset_id,
                metric=metric,
                level=level,
                value=value,
                threshold=threshold.alarm if level == "Alarm" else threshold.warning,
                unit=threshold.unit,
                source=threshold.source,
                triggered_at=datetime.now(timezone.utc),
                last_value=value,
                tier=getattr(threshold, "tier", 2),
                compliance_code=getattr(threshold, "compliance_code", None),
            )
            self._active[key] = alarm
            logger.warning(
                f"[AlarmManager] NEW {level.upper()} (Tier {alarm.tier}) | "
                f"{asset_id}.{metric} = {value:.2f} {threshold.unit}"
            )
            # Only auto-trigger Watchkeeper on Alarm level — Warnings are shown
            # on the dashboard but do NOT cascade the agent chain.
            if level == "Alarm":
                self._maybe_trigger_watchkeeper(asset_id, alarm)

        else:
            # Existing alarm — update value, escalate level if needed
            existing.last_value = value
            if level == "Alarm" and existing.level == "Warning":
                existing.level = "Alarm"
                existing.threshold = threshold.alarm
                logger.warning(
                    f"[AlarmManager] ESCALATED to ALARM (Tier {existing.tier}) | "
                    f"{asset_id}.{metric} = {value:.2f} {threshold.unit}"
                )
                self._maybe_trigger_watchkeeper(asset_id, existing)

    def _handle_resolved(self, key: tuple, asset_id: str, metric: str, value: float):
        alarm = self._active.pop(key, None)
        if alarm:
            duration = alarm.age_minutes
            logger.info(
                f"[AlarmManager] RESOLVED | {asset_id}.{metric} "
                f"returned to normal after {duration:.1f} min"
            )

    def _maybe_trigger_watchkeeper(self, asset_id: str, alarm: ActiveAlarm):
        """
        Queue a Watchkeeper trigger if this asset hasn't been investigated yet
        this fault cycle.  Fires exactly ONCE per fault event — subsequent
        threshold breaches on the same asset are suppressed until reset_asset()
        is called (i.e. the operator resets the asset / fleet).
        """
        # Tier 1 = Monitor only — show on dashboard, never cascade to agents.
        # This gate makes the documented tier semantics actually enforced.
        if alarm.tier < 2:
            logger.debug(
                f"[AlarmManager] Watchkeeper suppressed for {asset_id}.{alarm.metric} "
                f"— Tier 1 monitor-only (no agent cascade)"
            )
            return

        if asset_id in self._agent_fired:
            logger.debug(
                f"[AlarmManager] Watchkeeper suppressed for {asset_id} "
                f"— already under investigation (reset asset to clear)"
            )
            self.suppressed_queue.put({
                "asset_id": asset_id,
                "metric":   alarm.metric,
                "reason":   "already_investigating",
            })
            return

        self._agent_fired.add(asset_id)
        trigger = {
            "asset_id":        asset_id,
            "metric":          alarm.metric,
            "level":           alarm.level,
            "value":           alarm.last_value,
            "threshold":       alarm.threshold,
            "unit":            alarm.unit,
            "source":          alarm.source,
            "tier":            alarm.tier,
            "compliance_code": alarm.compliance_code,
            "reason": (
                f"{alarm.metric} = {alarm.last_value:.2f} {alarm.unit} "
                f"breached {alarm.level} limit {alarm.threshold} {alarm.unit} "
                f"({alarm.source})"
            ),
        }
        self.trigger_queue.put(trigger)

        # Freeze HF snapshot for ML analysis (captured outside the lock to avoid deadlock)
        try:
            from storage.hf_store import hf_store
            hf_store.capture_alarm_snapshot(asset_id)
            logger.info(f"[AlarmManager] HF snapshot captured for {asset_id}")
        except Exception as e:
            logger.warning(f"[AlarmManager] Could not capture HF snapshot for {asset_id}: {e}")

        logger.info(
            f"[AlarmManager] Watchkeeper trigger queued for {asset_id} "
            f"— {alarm.metric} (will not re-trigger until asset reset)"
        )

    # ── Read API for UI ────────────────────────────────────────────────────────

    def get_active_alarms(self) -> list[ActiveAlarm]:
        with self._lock:
            return sorted(
                self._active.values(),
                key=lambda a: (0 if a.level == "Alarm" else 1, a.triggered_at),
            )

    def acknowledge(self, asset_id: str, metric: str):
        """Mark alarm as seen by operator — does NOT clear it."""
        with self._lock:
            alarm = self._active.get((asset_id, metric))
            if alarm:
                alarm.acknowledged = True

    def reset_asset(self, asset_id: str):
        """
        Clear investigation state for one asset.
        Call this when the operator resets a specific asset so that the next
        fault injection on that asset will trigger a fresh Watchkeeper chain.
        """
        with self._lock:
            self._agent_fired.discard(asset_id)
            # Also clear any active alarms for this asset
            keys = [k for k in self._active if k[0] == asset_id]
            for k in keys:
                self._active.pop(k, None)
        logger.info(f"[AlarmManager] Asset reset — investigation flag cleared for {asset_id}")

    def clear_all(self):
        """Clear all active alarms and investigation flags — used on fleet reset."""
        with self._lock:
            count = len(self._active)
            self._active.clear()
            self._agent_fired.clear()
            # Drain the trigger queue so stale watchkeeper calls don't fire
            while not self.trigger_queue.empty():
                try:
                    self.trigger_queue.get_nowait()
                except Exception:
                    break
        if count:
            logger.info(f"[AlarmManager] Fleet reset — cleared {count} active alarm(s)")

    def force_trigger(self, asset_id: str):
        """
        Used by UI 'Run Watchkeeper' button — bypasses the fired-flag check.
        Builds the trigger payload from the current active alarm (if any) or
        a generic manual payload, puts it directly on the queue, and marks
        the asset as under investigation.
        """
        with self._lock:
            alarms = [a for a in self._active.values() if a.asset_id == asset_id]
            if alarms:
                alarm = alarms[0]
                trigger = {
                    "asset_id":        asset_id,
                    "metric":          alarm.metric,
                    "level":           alarm.level,
                    "value":           alarm.last_value,
                    "threshold":       alarm.threshold,
                    "unit":            alarm.unit,
                    "source":          alarm.source,
                    "tier":            getattr(alarm, "tier", 2),
                    "compliance_code": getattr(alarm, "compliance_code", None),
                    "reason": (
                        f"{alarm.metric} = {alarm.last_value:.2f} {alarm.unit} "
                        f"breached {alarm.level} limit {alarm.threshold} {alarm.unit} "
                        f"({alarm.source})"
                    ),
                }
            else:
                trigger = {
                    "asset_id": asset_id, "metric": "manual",
                    "level": "Info", "value": 0.0, "threshold": 0.0,
                    "unit": "", "source": "manual", "tier": 2,
                    "compliance_code": None,
                    "reason": "Manual trigger from UI",
                }
            self.trigger_queue.put(trigger)
            self._agent_fired.add(asset_id)   # suppress auto re-triggers after manual fire
        logger.info(f"[AlarmManager] Manual Watchkeeper trigger queued for {asset_id}")


# Module-level singleton — import this everywhere
alarm_manager = AlarmManager()
