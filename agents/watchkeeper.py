"""
Agent 1 — Realtime Watchkeeper  (v3.0 — Primary Orchestrator)
Maritime analogy: Chief Engineer directing the incident response chain

Triggered by AlarmManager when a sensor metric breaches a threshold.
Confirms the alarm, then orchestrates the full response chain by calling
subagent tools: diagnostics → planner → (compliance + fleet_intel if T3)
→ chain evaluator.
"""
from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from agents.tools import (
    TOOL_GET_FLEET_OVERVIEW, TOOL_GET_ASSET_HEALTH,
    TOOL_GET_TELEMETRY_TREND, TOOL_RAISE_ALERT,
    TOOL_CALL_DIAGNOSTICS, TOOL_CALL_PLANNER,
    TOOL_CALL_COMPLIANCE, TOOL_CALL_FLEET_INTEL,
    TOOL_CALL_EVALUATOR,
)


class RealtimeWatchkeeper(BaseAgent):

    name = "realtime_watchkeeper"
    role_title = "Chief Engineer (AI Orchestrator)"
    max_tool_rounds = 30
    max_tokens = 8192

    def _build_system_prompt(self) -> str:
        return """You are the AI Realtime Watchkeeper aboard MV-Callisto, acting as the Chief Engineer orchestrating the incident response chain.

You are triggered automatically when a sensor metric breaches a defined threshold. You are the PRIMARY ORCHESTRATOR — you confirm the alarm and then direct the full response chain by calling specialist agents.

## YOUR MANDATORY WORKFLOW

### STEP 1 — CONFIRM THE ALARM
Call get_asset_health(asset_id) and get_telemetry_trend(asset_id, tag) to verify the breach.
- Check if the breach is sustained (real) vs. a transient spike (sensor noise).
- Cross-correlate with related sensors to understand the pattern.
- Call raise_alert() with the correct severity:
  - Warning limit only → "Warning"
  - Alarm limit breached → "Alarm"
  - SOLAS-critical (COMP-001, AUXGEN-001) at Alarm → "Critical"
  - Multiple simultaneous breaches on one asset → "Critical"

### STEP 2 — ESCALATE TO DEEP DIAGNOSTICS
Unless the breach is clearly sensor noise, call call_deep_diagnostics(asset_id, reason, severity).
- Pass your cross-correlation findings as the reason (2–3 sentences).
- Wait for the diagnostic report before proceeding.

### STEP 3 — CREATE WORK ORDER
Unless diagnostics returned "normal/healthy" (no fault), call call_maintenance_planner(asset_id, diagnostic_summary).
- Summarise the diagnostic report for the planner.

### STEP 4 — COMPLIANCE AND FLEET INTEL (ALL incidents — mandatory)
Always call BOTH of these agents for every incident, regardless of tier:
- Call call_compliance_check(asset_id, context) — assess ISM/SOLAS obligations for the affected asset.
- Call call_fleet_intelligence(asset_id) — retrieve fleet-wide patterns and advisory.
Both calls can be made in either order (they are independent).

### STEP 5 — CHAIN EVALUATION (ALWAYS LAST)
After all other steps are complete, ALWAYS call call_chain_evaluator(incident_id, chain_summary).
- Provide a 1–2 sentence chain_summary of what was found and decided.
- This step is mandatory for every chain, regardless of tier.

## CRITICAL RULES — CHECK BEFORE EVERY RESPONSE
- Complete ALL 5 steps in order — do not skip any, regardless of tier.
- Steps 4 (compliance + fleet_intel) are MANDATORY for every incident — not just SOLAS/Tier 3.
- When calling call_maintenance_planner, always include full_diagnostic_report (copy the full_report from diagnostics response) and watchkeeper_assessment (your own cross-correlated alarm assessment).
- **After fleet_intel completes, your VERY NEXT tool call MUST be call_chain_evaluator. Do not write any text response first.**
- Pass the exact incident_id from the trigger to call_chain_evaluator.
- If a subagent returns an error, note it but continue to the next step.
- NEVER end your loop without calling call_chain_evaluator — it is mandatory for every chain.
- Only write your final watch log text AFTER call_chain_evaluator has returned a result."""

    def _get_tools(self) -> list[dict]:
        return [
            TOOL_GET_FLEET_OVERVIEW,
            TOOL_GET_ASSET_HEALTH,
            TOOL_GET_TELEMETRY_TREND,
            TOOL_RAISE_ALERT,
            TOOL_CALL_DIAGNOSTICS,
            TOOL_CALL_PLANNER,
            TOOL_CALL_COMPLIANCE,
            TOOL_CALL_FLEET_INTEL,
            TOOL_CALL_EVALUATOR,
        ]

    def _build_user_message(self, trigger: dict | None = None) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        incident_id = (trigger or {}).get("incident_id", "UNKNOWN")
        tier        = (trigger or {}).get("tier", 2)
        tier_label  = "TIER 3 — SOLAS/ISM CRITICAL" if tier >= 3 else "TIER 2 — INVESTIGATE"

        if trigger and trigger.get("asset_id") and trigger.get("metric") != "manual":
            asset_id      = trigger["asset_id"]
            metric        = trigger["metric"]
            level         = trigger["level"]
            value         = trigger["value"]
            threshold     = trigger["threshold"]
            unit          = trigger["unit"]
            source        = trigger.get("source", "")
            compliance_code = trigger.get("compliance_code", "")
            compliance_note = f"\nCompliance code: {compliance_code}" if compliance_code else ""
            return (
                f"THRESHOLD BREACH — {now}\n"
                f"Incident ID: {incident_id} | {tier_label}\n"
                f"Asset: {asset_id}\n"
                f"Metric: {metric} = {value:.2f} {unit}\n"
                f"Breached: {level} limit {threshold} {unit} ({source})"
                f"{compliance_note}\n\n"
                f"Execute the FULL 5-step incident response chain (mandatory for ALL tiers):\n"
                f"1. Confirm alarm (get_asset_health + get_telemetry_trend + raise_alert)\n"
                f"2. call_deep_diagnostics → wait for full diagnostic report\n"
                f"3. call_maintenance_planner — pass full_diagnostic_report + watchkeeper_assessment\n"
                f"4. call_compliance_check + call_fleet_intelligence (BOTH, in any order)\n"
                f"5. call_chain_evaluator(incident_id='{incident_id}') — ALWAYS LAST\n\n"
                f"Always end with call_chain_evaluator using incident_id='{incident_id}'."
            )

        if trigger and trigger.get("asset_id"):
            asset_id = trigger["asset_id"]
            return (
                f"Watch check requested for {asset_id} — {now}\n"
                f"Incident ID: {incident_id} | {tier_label}\n\n"
                f"Review asset condition, check for anomalies, raise alerts where warranted, "
                f"then execute the full chain. Always end with "
                f"call_chain_evaluator(incident_id='{incident_id}')."
            )

        return (
            f"Engine room watch check — {now}. Vessel: MV-Callisto.\n"
            f"Incident ID: {incident_id} | {tier_label}\n\n"
            "Perform a systematic watch round across all assets. Raise alerts where warranted. "
            f"If any anomalies are found, run the full chain. "
            f"Always end with call_chain_evaluator(incident_id='{incident_id}')."
        )
