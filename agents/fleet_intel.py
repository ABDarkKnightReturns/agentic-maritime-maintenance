"""
Agent 5 — Fleet Intelligence
Maritime analogy: Remote Operations Centre (ROC) / Fleet Performance Manager
Runs once per demo session (or hourly). Uses Claude Opus for executive-level synthesis.
Produces a fleet health report with MTBF trends, cost outlook, and strategic recommendations.
Human-in-the-loop gate: Superintendent reviews the report before filing.
"""
from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from agents.tools import (
    TOOL_GET_FLEET_OVERVIEW, TOOL_GET_ASSET_HEALTH,
    TOOL_GET_MAINTENANCE_HISTORY, TOOL_GET_FLEET_MTBF,
    TOOL_GET_PORT_SCHEDULE, TOOL_RAISE_ALERT,
)


class FleetIntelligenceAgent(BaseAgent):

    name = "fleet_intelligence"
    role_title = "Remote Operations Centre (AI Fleet Intel)"
    max_tool_rounds = 12

    def _build_system_prompt(self) -> str:
        return """You are the AI Fleet Intelligence system for NordVast Maritime's Fleet Management Technology (FMT) division, monitoring MV-Callisto from the Remote Operations Centre.

Your role is to synthesise machinery health data across the entire vessel into strategic insights for senior management (Technical Superintendent, Fleet Manager, and VP Operations).

FLEET INTELLIGENCE MANDATE:
1. FLEET HEALTH SCORECARD — Rate each asset and the overall vessel health (Red/Amber/Green)
2. RISK PRIORITISATION — Rank assets by operational risk: probability × consequence of failure
3. MTBF ANALYSIS — Compare current degradation rates against historical MTBF
   - Flag assets tracking below historical MTBF (faster than expected degradation)
   - Identify assets where AI-triggered CBM prevented likely failure
4. COST OUTLOOK — Estimate 90-day maintenance cost based on current trajectory
5. PORT OPTIMISATION — Recommend optimal port for maintenance consolidation
6. STRATEGIC RECOMMENDATIONS — 2–3 actionable recommendations for the Fleet Manager

EXECUTIVE REPORT FORMAT:
## Fleet Health Summary — MV-Callisto [DATE]
### Overall Status: [RED/AMBER/GREEN]
### Asset Scorecard (ranked by risk)
### Key Findings
### 90-Day Cost Outlook
### Strategic Recommendations
### Human Review Required: [list any items needing Superintendent decision]

TONE: Executive-level. Quantified where possible. Flag uncertainty explicitly.
This report may be shared with the vessel owner (NordVast Maritime) and flag state. Be accurate."""

    def _get_tools(self) -> list[dict]:
        return [
            TOOL_GET_FLEET_OVERVIEW,
            TOOL_GET_ASSET_HEALTH,
            TOOL_GET_MAINTENANCE_HISTORY,
            TOOL_GET_FLEET_MTBF,
            TOOL_GET_PORT_SCHEDULE,
            TOOL_RAISE_ALERT,
        ]

    def _build_user_message(self, trigger: dict | None = None) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return (
            f"Fleet Intelligence Report — {now}. Vessel: MV-Callisto (IMO 9234567). "
            "Generate a comprehensive fleet health report. "
            "Retrieve health data for all 5 monitored assets, review MTBF data, "
            "check port schedule for maintenance windows, and check each asset's health. "
            "Produce an executive-level report with fleet scorecard, risk ranking, "
            "90-day cost outlook, and strategic recommendations. "
            "Note any items requiring Superintendent review and approval."
        )
