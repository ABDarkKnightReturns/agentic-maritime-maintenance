"""
Agent 3 — Maintenance Planner
Maritime analogy: Technical Superintendent at shore-side management
Triggered after diagnostics. Creates draft work orders optimised for port windows.
Human-in-the-loop gate: Chief Engineer must approve before scheduling.
"""
from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from agents.tools import (
    TOOL_GET_ASSET_HEALTH, TOOL_GET_FLEET_OVERVIEW,
    TOOL_GET_MAINTENANCE_HISTORY, TOOL_GET_RECENT_ALERTS,
    TOOL_GET_PORT_SCHEDULE, TOOL_CREATE_WORK_ORDER, TOOL_KB_RETRIEVE,
)


class MaintenancePlannerAgent(BaseAgent):

    name = "maintenance_planner"
    role_title = "Technical Superintendent (AI Planner)"
    max_tool_rounds = 10

    def _build_system_prompt(self) -> str:
        return """You are an AI Technical Superintendent for MV-Callisto, responsible for maintenance planning and optimisation.

Your role is to translate diagnostic findings into actionable maintenance work orders that are:
- Timed to align with port calls (minimise off-hire time)
- Prioritised by risk to vessel operation and safety
- Resourced with realistic time and cost estimates
- Compliant with PMS (Planned Maintenance System) requirements

PLANNING PRINCIPLES:
1. PRIORITISE by consequence of failure:
   - Safety-critical (SOLAS): Priority 1 — Emergency or Critical
   - Class-required: Priority 2 — High
   - Operational impact > 20%: Priority 2–3
   - Minor efficiency loss: Priority 4–5

2. TIMING windows:
   - Critical: Within 48 hours regardless of port
   - High: Next port call
   - Medium: Within 30 days, at a suitable port
   - Low: Next scheduled dry dock or convenience

3. WORK ORDER content — each WO must include:
   - Clear scope of work
   - Technical justification (sensor data and trend analysis)
   - Whether it can be done at sea or requires port
   - Whether a class surveyor is needed
   - Realistic hours and cost estimate

4. CONSOLIDATION: If two assets need work at the same port, mention this for crew planning.

5. PORT ALIGNMENT: Always call get_port_schedule and recommend a specific port call.

MANDATORY WORKFLOW — YOU MUST FOLLOW THIS EXACTLY:
Step 1: Gather context — call get_asset_health, get_maintenance_history, get_recent_alerts, get_port_schedule, and kb_retrieve as needed.
Step 2: Call create_work_order — YOU MUST call this tool to create the work order. Do NOT end your response without calling create_work_order first. Thinking about creating a WO is not enough — you MUST call the tool.
Step 3: After create_work_order returns successfully, summarise the work order details and state: "These work orders require Chief Engineer approval before scheduling."

CRITICAL: Never end your turn without having called create_work_order. If you have gathered all the diagnostic information you need, your next action MUST be to call create_work_order — not to write text about what you plan to do.
Do NOT mark anything as approved — that is a human decision."""

    def _get_tools(self) -> list[dict]:
        return [
            TOOL_GET_FLEET_OVERVIEW,
            TOOL_GET_ASSET_HEALTH,
            TOOL_GET_MAINTENANCE_HISTORY,
            TOOL_GET_RECENT_ALERTS,
            TOOL_GET_PORT_SCHEDULE,
            TOOL_CREATE_WORK_ORDER,
            TOOL_KB_RETRIEVE,
        ]

    def _build_user_message(self, trigger: dict | None = None) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if trigger and trigger.get("asset_id"):
            asset_id         = trigger["asset_id"]
            diag_summary     = trigger.get("diagnostic_summary", "anomaly detected")
            full_diag_report = trigger.get("full_diagnostic_report", "")
            wk_assessment    = trigger.get("watchkeeper_assessment", "")

            context_block = f"Diagnostic summary: {diag_summary}"
            if full_diag_report:
                context_block += f"\n\nFull diagnostic report from Deep Diagnostics:\n{full_diag_report}"
            if wk_assessment:
                context_block += f"\n\nWatchkeeper assessment:\n{wk_assessment}"

            return (
                f"Maintenance planning triggered for {asset_id} — {now}.\n\n"
                f"{context_block}\n\n"
                "Use the diagnostic findings above as your primary input — do NOT re-derive the fault "
                "or contradict the diagnostic report. Your job is to translate these findings into a "
                "work order that is correctly timed, resourced, and scoped.\n\n"
                "Follow the mandatory workflow:\n"
                "(1) Gather supplementary context — call get_asset_health, get_maintenance_history, "
                "get_recent_alerts, get_port_schedule, and kb_retrieve.\n"
                "(2) Call create_work_order — you MUST call this tool. Do not end without calling it.\n"
                "(3) After create_work_order succeeds, summarise the WO and note CE approval is required."
            )
        return (
            f"Maintenance planning cycle — {now}. Vessel: MV-Callisto. "
            "Review all assets, identify those requiring maintenance intervention, "
            "align with the port schedule, and call create_work_order for any assets "
            "that need attention within the next 30 days. "
            "You MUST call create_work_order for each asset that needs work — do not just describe work orders, create them. "
            "Prioritise by risk and operational impact."
        )
