"""
Incident Record — structured audit trail for one alarm-triggered agent chain.

Each time the AlarmManager fires a Tier 2 or Tier 3 trigger, an IncidentRecord
is created and progressively filled as each agent in the chain completes its work.

Tier 2: Watchkeeper → Deep Diagnostics → Maintenance Planner
Tier 3: Watchkeeper → Deep Diagnostics → Maintenance Planner
             └─ (parallel) ISM Compliance + Fleet Intelligence
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Any


@dataclass
class AgentStep:
    """One agent's contribution to the incident chain."""
    agent_name: str        # watchkeeper / diagnostics / planner / compliance / fleet_intel
    icon: str
    label: str             # display label
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tool_calls: int = 0
    summary: str = ""      # one-line summary for dossier display
    full_output: str = ""  # complete agent reasoning — shown in Incidents tab expander
    status: str = "pending"  # pending / running / done / skipped

    @property
    def duration_s(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def time_str(self) -> str:
        if self.started_at:
            return self.started_at.strftime("%H:%M:%S")
        return "—"


@dataclass
class IncidentRecord:
    """
    Full lifecycle record for one alarm-triggered incident.
    Created by IncidentStore; updated as each agent step completes.
    """
    incident_id: str          # INC-2026-NNN
    asset_id: str
    metric: str
    tier: int                 # 2 = Investigate, 3 = Critical/SOLAS
    compliance_code: Optional[str]  # e.g. "SOLAS-II-1/28"
    triggered_at: datetime
    trigger_value: float
    trigger_threshold: float
    trigger_unit: str
    trigger_level: str        # "Alarm" / "Warning"

    # Agent chain steps — populated progressively
    steps: dict[str, AgentStep] = field(default_factory=dict)

    # Quick-access fields set by store convenience methods
    wo_id: Optional[str] = None       # work order ID from planner
    compliance_status: Optional[str] = None  # COMPLIANT / MINOR NC / MAJOR NC
    fleet_advisory: Optional[str] = None

    status: str = "Open"              # Open / Pending Approval / Resolved
    resolved_at: Optional[datetime] = None

    # ML analysis result — populated when Diagnostics calls get_hf_analysis
    ml_result: Optional[Any] = None   # MLAnalysisResult from ml.models

    # Evaluator score — set by EvaluatorAgent at chain end (0–100)
    evaluator_score: Optional[int] = None

    def __post_init__(self):
        # Full 6-agent chain runs for ALL incidents regardless of tier.
        # ISM Compliance and Fleet Intelligence provide value even for
        # non-SOLAS alarms (maintenance history patterns, fleet-wide context).
        all_steps = [
            AgentStep("watchkeeper",  "🔭", "Watchkeeper"),
            AgentStep("diagnostics",  "🔬", "Deep Diagnostics"),
            AgentStep("planner",      "📋", "Maintenance Planner"),
            AgentStep("compliance",   "⚖️",  "ISM Compliance"),
            AgentStep("fleet_intel",  "🌐", "Fleet Intelligence"),
            AgentStep("evaluator",    "⚡", "Chain Evaluator"),
        ]
        for s in all_steps:
            s.status = "pending"
            self.steps[s.agent_name] = s

    @property
    def tier_label(self) -> str:
        if self.tier >= 3:
            return f"TIER 3 — SOLAS/ISM Critical ({self.compliance_code or ''})"
        return "TIER 2 — Investigate"

    @property
    def tier_color(self) -> str:
        return "#D50000" if self.tier >= 3 else "#FF6D00"

    @property
    def age_minutes(self) -> float:
        return (datetime.now(timezone.utc) - self.triggered_at).total_seconds() / 60

    @property
    def chain_complete(self) -> bool:
        return all(
            s.status in ("done", "skipped")
            for s in self.steps.values()
        )

    @property
    def steps_done(self) -> int:
        return sum(1 for s in self.steps.values() if s.status == "done")

    @property
    def steps_total_active(self) -> int:
        return sum(1 for s in self.steps.values() if s.status != "skipped")
