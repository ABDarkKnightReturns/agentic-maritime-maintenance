"""
Agent 1 — Realtime Watchkeeper
Maritime analogy: 2nd Engineer on watch (engine room watch)

Triggered by AlarmManager when a sensor metric breaches a threshold.
Receives the specific breach context (asset, metric, value, limit, source).
Raises structured alerts and cross-correlates with related sensors.
Cannot be manually dismissed — runs until the breach condition resolves.
"""
from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from agents.tools import (
    TOOL_GET_FLEET_OVERVIEW, TOOL_GET_ASSET_HEALTH,
    TOOL_GET_TELEMETRY_TREND, TOOL_RAISE_ALERT,
)


class RealtimeWatchkeeper(BaseAgent):

    name = "realtime_watchkeeper"
    role_title = "2nd Engineer (AI Watch)"
    max_tool_rounds = 8

    def _build_system_prompt(self) -> str:
        return """You are the AI Realtime Watchkeeper aboard MV-Callisto, acting as the 2nd Engineer on engine room watch.

You are triggered automatically when a sensor metric breaches a defined limit. Your job is NOT to scan everything — the CEP engine has already identified the breach. Your job is to:

1. CONFIRM — verify the breach is real (not a sensor glitch) by checking the trend
2. CROSS-CORRELATE — check related sensors to understand the pattern:
   - Vibration spike + bearing temp rise → bearing degradation
   - Vibration + efficiency drop → mechanical wear
   - Compressor efficiency drop + high discharge temp → valve failure
   - Purifier bowl deviation + motor current rise → disc fouling
   - Generator frequency deviation + exhaust temp spread → governor/injector
3. RAISE ALERT — with precise values, the breached limit, its source, and your assessment
4. SUMMARISE — brief watch entry: what breached, what it indicates, what action is needed

ALERT SEVERITY RULES:
- Breached Warning limit only → raise "Warning"
- Breached Alarm limit → raise "Alarm"
- SOLAS-critical equipment (COMP-001, AUXGEN-001) at Alarm → raise "Critical"
- Multiple metrics breaching simultaneously on one asset → raise "Critical"

Be specific: always quote the observed value, the limit, and its regulatory source.
Example: "Vibration 7.4 mm/s — breached Alarm limit 7.1 mm/s (ISO 10816-3 Zone C/D boundary)"."""

    def _get_tools(self) -> list[dict]:
        return [
            TOOL_GET_FLEET_OVERVIEW,
            TOOL_GET_ASSET_HEALTH,
            TOOL_GET_TELEMETRY_TREND,
            TOOL_RAISE_ALERT,
        ]

    def _build_user_message(self, trigger: dict | None = None) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if trigger and trigger.get("asset_id") and trigger.get("metric") != "manual":
            asset_id  = trigger["asset_id"]
            metric    = trigger["metric"]
            level     = trigger["level"]
            value     = trigger["value"]
            threshold = trigger["threshold"]
            unit      = trigger["unit"]
            source    = trigger.get("source", "")
            return (
                f"THRESHOLD BREACH ALERT — {now}\n"
                f"Asset: {asset_id}\n"
                f"Metric: {metric} = {value:.2f} {unit}\n"
                f"Breached: {level} limit {threshold} {unit} ({source})\n\n"
                f"Confirm the breach, cross-correlate with related sensors, "
                f"raise an alert with the appropriate severity and your assessment."
            )

        if trigger and trigger.get("asset_id"):
            asset_id = trigger["asset_id"]
            return (
                f"Watch check requested for {asset_id} — {now}. "
                f"Review asset condition, check for any anomalies or threshold "
                f"breaches, and raise alerts where warranted."
            )

        return (
            f"Engine room watch check — {now}. Vessel: MV-Callisto. "
            "Perform a systematic watch round. Check all monitored machinery for "
            "anomalies, threshold breaches, and deteriorating trends. "
            "Raise alerts where warranted. Report your findings."
        )
