"""
Incident Store — module-level singleton, survives Streamlit re-runs.

Thread-safe store for IncidentRecord objects. Created when the alarm
chain fires; updated as each agent step completes.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional

from models.incident import IncidentRecord, AgentStep

_store: dict[str, IncidentRecord] = {}
_lock = threading.Lock()
_counter = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    year = datetime.now(timezone.utc).year
    return f"INC-{year}-{_counter:03d}"


# ── Create ────────────────────────────────────────────────────────────────────

def create_incident(trigger: dict) -> IncidentRecord:
    """Create a new IncidentRecord from an AlarmManager trigger dict."""
    inc = IncidentRecord(
        incident_id=_next_id(),
        asset_id=trigger.get("asset_id", "unknown"),
        metric=trigger.get("metric", "unknown"),
        tier=trigger.get("tier", 2),
        compliance_code=trigger.get("compliance_code"),
        triggered_at=datetime.now(timezone.utc),
        trigger_value=trigger.get("value", 0.0),
        trigger_threshold=trigger.get("threshold", 0.0),
        trigger_unit=trigger.get("unit", ""),
        trigger_level=trigger.get("level", "Alarm"),
    )
    with _lock:
        _store[inc.incident_id] = inc
    return inc


# ── Step updates ──────────────────────────────────────────────────────────────

def start_step(incident_id: str, agent_name: str) -> None:
    with _lock:
        inc = _store.get(incident_id)
        if inc and agent_name in inc.steps:
            inc.steps[agent_name].status = "running"
            inc.steps[agent_name].started_at = datetime.now(timezone.utc)


def complete_watchkeeper(incident_id: str, summary: str, tool_calls: int = 0,
                         full_output: str = "") -> None:
    _complete_step(incident_id, "watchkeeper", summary, tool_calls, full_output)


def complete_ml_analysis(incident_id: str, ml_result, tool_calls: int = 0) -> None:
    """Store ML pipeline result and mark the ml_analysis step done."""
    summary = (
        f"{ml_result.fault_class.replace('_',' ')} p={ml_result.fault_probability:.2f} "
        f"· anomaly={ml_result.anomaly_score:.2f} · RUL={ml_result.rul_days:.1f}d"
        if ml_result and not ml_result.error
        else (ml_result.error if ml_result else "ML analysis failed")
    )
    _complete_step(incident_id, "ml_analysis", summary[:200], tool_calls,
                   ml_result.narrative if ml_result else "")
    with _lock:
        inc = _store.get(incident_id)
        if inc and ml_result:
            inc.ml_result = ml_result


def complete_diagnostics(incident_id: str, summary: str, tool_calls: int = 0,
                         full_output: str = "") -> None:
    _complete_step(incident_id, "diagnostics", summary, tool_calls, full_output)


def complete_planner(incident_id: str, summary: str, wo_id: Optional[str],
                     tool_calls: int = 0, full_output: str = "") -> None:
    _complete_step(incident_id, "planner", summary, tool_calls, full_output)
    with _lock:
        inc = _store.get(incident_id)
        if inc and wo_id:
            inc.wo_id = wo_id
            inc.status = "Pending WO Approval"


def complete_compliance(incident_id: str, summary: str, status: str,
                        tool_calls: int = 0, full_output: str = "") -> None:
    _complete_step(incident_id, "compliance", summary, tool_calls, full_output)
    with _lock:
        inc = _store.get(incident_id)
        if inc:
            inc.compliance_status = status


def complete_fleet_intel(incident_id: str, advisory: str, tool_calls: int = 0,
                         full_output: str = "") -> None:
    _complete_step(incident_id, "fleet_intel", advisory, tool_calls, full_output)
    with _lock:
        inc = _store.get(incident_id)
        if inc:
            inc.fleet_advisory = advisory


def _complete_step(incident_id: str, agent_name: str,
                   summary: str, tool_calls: int, full_output: str = "") -> None:
    with _lock:
        inc = _store.get(incident_id)
        if inc and agent_name in inc.steps:
            step = inc.steps[agent_name]
            step.status = "done"
            step.completed_at = datetime.now(timezone.utc)
            step.summary = summary[:200]
            step.full_output = full_output  # full reasoning — no truncation
            step.tool_calls = tool_calls
            # If all active steps done → mark incident chain complete
            if inc.chain_complete and inc.status == "Open":
                inc.status = "Chain Complete"


# ── Read API ──────────────────────────────────────────────────────────────────

def get_all(limit: int = 20) -> list[IncidentRecord]:
    with _lock:
        incidents = sorted(_store.values(),
                           key=lambda i: i.triggered_at, reverse=True)
        return incidents[:limit]


def get_active() -> list[IncidentRecord]:
    with _lock:
        return [i for i in _store.values()
                if i.status not in ("Resolved",)]


def get_by_id(incident_id: str) -> Optional[IncidentRecord]:
    with _lock:
        return _store.get(incident_id)


def resolve_incident(incident_id: str) -> None:
    with _lock:
        inc = _store.get(incident_id)
        if inc:
            inc.status = "Resolved"
            inc.resolved_at = datetime.now(timezone.utc)


def clear_all() -> None:
    global _counter
    with _lock:
        _store.clear()
        _counter = 0
