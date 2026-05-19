"""
Agent 4 — ISM Compliance Checker
Maritime analogy: DPA (Designated Person Ashore) / ISM Manager
Triggered when a work order is created or on weekly schedule.
Checks ISM Code compliance, class survey due dates, and regulatory obligations.
"""
from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from agents.tools import (
    TOOL_GET_ASSET_HEALTH, TOOL_GET_FLEET_OVERVIEW,
    TOOL_GET_MAINTENANCE_HISTORY, TOOL_GET_ISM_REQUIREMENTS,
    TOOL_RAISE_ALERT, TOOL_KB_RETRIEVE,
)


class ISMComplianceAgent(BaseAgent):

    name = "ism_compliance"
    role_title = "DPA / ISM Manager (AI Compliance)"
    max_tool_rounds = 8

    def _build_system_prompt(self) -> str:
        return """You are an AI ISM Compliance Manager for MV-Callisto, acting as the Designated Person Ashore (DPA).

Your responsibilities under ISM Code (International Safety Management Code, SOLAS Chapter IX):
- Section 10: Maintenance of the Ship and Equipment
- Section 10.1: Ensure equipment is maintained in accordance with applicable rules
- Section 10.3: Establish safeguards for identified non-conformities

COMPLIANCE ASSESSMENT FRAMEWORK:
1. For each asset showing degradation, check ISM maintenance requirements
2. Identify if current condition represents a non-conformity (NC) under ISM
3. Flag if Class society notification is required (DNV class rules)
4. Check if SOLAS-critical equipment (starting air, generators) is within safe operating limits
5. Identify if a Port State Control (PSC) inspector would raise a deficiency

NON-CONFORMITY THRESHOLDS:
- Any SOLAS-critical equipment (starting air compressor, emergency generator) below healthy → potential major NC
- Class-required survey overdue → NC requiring immediate rectification
- Maintenance interval exceeded by > 10% → minor NC
- Running hours significantly above PMS trigger → non-conformity risk

REPORTING FORMAT:
- State compliance status: COMPLIANT / MINOR NC / MAJOR NC / SOLAS VIOLATION
- Reference specific ISM Code sections and class rules
- State whether DNV or flag state notification is required
- Recommend corrective action with deadline

Use kb_retrieve to look up specific SOLAS/MARPOL/IACS requirements and cite the exact regulation when declaring a non-conformity. A PSC inspector expects precise regulatory references — "SOLAS II-1/28.1 requires minimum 12 starts" is far more compelling than a vague claim.

You are the last line of defence before a PSC inspection. Be rigorous and conservative."""

    def _get_tools(self) -> list[dict]:
        return [
            TOOL_GET_FLEET_OVERVIEW,
            TOOL_GET_ASSET_HEALTH,
            TOOL_GET_MAINTENANCE_HISTORY,
            TOOL_GET_ISM_REQUIREMENTS,
            TOOL_RAISE_ALERT,
            TOOL_KB_RETRIEVE,
        ]

    def _build_user_message(self, trigger: dict | None = None) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if trigger and trigger.get("asset_id"):
            asset_id = trigger["asset_id"]
            return (
                f"ISM compliance review requested for {asset_id} — {now}. "
                f"Context: {trigger.get('context', 'work order created for this asset')}. "
                "Retrieve ISM requirements for this equipment type. "
                "Assess current condition against requirements. "
                "Identify any non-conformities and state the regulatory obligation."
            )
        return (
            f"Weekly ISM compliance check — {now}. Vessel: MV-Callisto. "
            "Review all monitored assets for ISM compliance. "
            "For any asset showing degradation, check requirements and identify "
            "non-conformities. Flag any SOLAS-critical concerns immediately. "
            "Provide compliance status for each asset."
        )
