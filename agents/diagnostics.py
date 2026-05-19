"""
Agent 2 — Deep Diagnostics & RUL
Maritime analogy: Chief Engineer performing systematic machinery assessment
Runs hourly or on-demand for a specific asset showing anomalies.
Performs root cause analysis, estimates Remaining Useful Life, recommends action.

v2.0: Upgraded to use HF ML analysis (get_hf_analysis tool) as primary evidence source.
Claude now reasons over ML evidence (Isolation Forest anomaly score, rule-based fault
classification, FFT spectral features) PLUS CEP sensor trends and KB standards.
"""
from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from agents.tools import (
    TOOL_GET_ASSET_HEALTH, TOOL_GET_TELEMETRY_TREND,
    TOOL_GET_RECENT_ALERTS, TOOL_GET_MAINTENANCE_HISTORY,
    TOOL_GET_FLEET_OVERVIEW, TOOL_KB_RETRIEVE,
    TOOL_GET_HF_ANALYSIS,
)


class DeepDiagnosticsAgent(BaseAgent):

    name = "deep_diagnostics"
    role_title = "Chief Engineer (AI Diagnostics)"
    max_tool_rounds = 12

    def _build_system_prompt(self) -> str:
        return """You are an expert AI Chief Engineer aboard MV-Callisto, specialising in predictive diagnostics and reliability engineering. You have 20 years of experience with marine diesel engines, rotating equipment, and condition monitoring.

Your role is to perform deep technical analysis on machinery showing signs of degradation.

## v2.0 UPGRADED DIAGNOSTIC FRAMEWORK

You now have access to HIGH-FREQUENCY (10 Hz) ML ANALYSIS via the get_hf_analysis tool.
This provides machine-learning evidence from 120 seconds of vibration and sensor data:
  - Isolation Forest anomaly detection score (0.0–1.0)
  - Rule-based fault classification with probabilities (bearing_wear, cavitation, imbalance, misalignment, looseness, seal_leak, fouling, normal)
  - FFT spectral features: dominant frequency, spectral centroid, band power ratios
  - Statistical features: kurtosis (bearing defect: >4 warning, >8 severe), crest factor (impulsive: >6 warning)
  - RUL estimate from vibration trend slope

## MANDATORY DIAGNOSTIC WORKFLOW

Step 1: **ML EVIDENCE FIRST** — Call get_hf_analysis(asset_id) as your FIRST tool call.
        This provides the foundation of your diagnosis. An anomaly_score > 0.65 means
        the ML model has detected a statistically significant deviation from healthy baseline.

Step 2: **CEP CORROBORATION** — Call get_asset_health(asset_id) to get CEP-derived health
        score, RUL, efficiency metrics, and sensor readings for cross-correlation.

Step 3: **TREND ANALYSIS** — Call get_telemetry_trend() for 1–2 key tags that the ML
        analysis has flagged (e.g. bearing_temp_c if bearing_wear detected).

Step 4: **KB GROUNDING** — Call kb_retrieve() with a query that includes the ML fault class
        and key features (e.g. "bearing wear kurtosis 7.3 BPFI pump ISO 13373").

Step 5: **MAINTENANCE CONTEXT** — Call get_maintenance_history() and get_recent_alerts()
        to establish baseline and identify if this pattern is recurring.

Step 6: **SYNTHESISE & CONCLUDE** — Produce your root cause analysis. Structure it as:

### ML EVIDENCE
State the anomaly score, fault class, probability, and key features (kurtosis, crest factor, dominant frequency).
Interpret what these mean physically.

### CEP CORROBORATION
Confirm or qualify the ML finding with 1 Hz sensor trends.

### ROOT CAUSE
State the most likely failure mechanism. If kurtosis > 4 and bearing_wear probability > 0.6,
explain the bearing defect frequency theory. Reference ISO standards from kb_retrieve.

### RUL ESTIMATE
Quote the ML pipeline RUL and the CEP RUL. State which is more conservative and why.
Give confidence level (high/medium/low) with explicit assumptions.

### RECOMMENDATION
Specify: inspect / overhaul / replace, with urgency (immediate / next port / within 30 days).
State whether class surveyor notification is required.

## ENGINEERING STANDARDS
- Always cite technical references from kb_retrieve (ISO 10816-3, ISO 13373-3, OEM manuals)
- Flag SOLAS/ISM compliance implications if safety-critical
- Use engineering units throughout
- Kurtosis interpretation: 3 = Gaussian (healthy), 4–8 = developing defect, >8 = severe
- Crest factor interpretation: 2–3 = normal, 4–6 = developing impulsive fault, >6 = severe"""

    def _get_tools(self) -> list[dict]:
        return [
            TOOL_GET_HF_ANALYSIS,          # NEW — call first
            TOOL_GET_ASSET_HEALTH,
            TOOL_GET_TELEMETRY_TREND,
            TOOL_GET_RECENT_ALERTS,
            TOOL_GET_MAINTENANCE_HISTORY,
            TOOL_GET_FLEET_OVERVIEW,
            TOOL_KB_RETRIEVE,
        ]

    def _build_user_message(self, trigger: dict | None = None) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if trigger and trigger.get("asset_id"):
            asset_id = trigger["asset_id"]
            reason   = trigger.get("reason", "elevated anomaly score")

            # Include ML pre-analysis summary if passed from cascade
            ml_context = ""
            if trigger.get("ml_fault_class") and trigger["ml_fault_class"] != "normal":
                ml_context = (
                    f"\n\nPRE-ANALYSIS ML RESULT (from ML pipeline):\n"
                    f"Fault class: {trigger['ml_fault_class']}\n"
                    f"ML narrative: {trigger.get('ml_narrative', 'not available')[:500]}\n"
                    f"Use get_hf_analysis to retrieve the full ML result with all features."
                )

            return (
                f"Deep diagnostic analysis requested for {asset_id} — {now}. "
                f"Trigger: {reason}.{ml_context}\n\n"
                "MANDATORY WORKFLOW:\n"
                "1. Call get_hf_analysis first — this is your primary evidence source.\n"
                "2. Call get_asset_health for CEP corroboration.\n"
                "3. Call get_telemetry_trend for 1–2 tags highlighted by the ML result.\n"
                "4. Call kb_retrieve with the ML fault class as search term.\n"
                "5. Call get_maintenance_history and get_recent_alerts.\n"
                "6. Produce structured root cause analysis per the diagnostic framework.\n"
                "Be technically rigorous. A Chief Engineer will review your findings."
            )
        return (
            f"Hourly machinery assessment — {now}. Vessel: MV-Callisto. "
            "Run get_hf_analysis for all assets or focus on assets with highest anomaly. "
            "Review the health of all monitored assets using the full diagnostic workflow. "
            "Focus your deep analysis on the 1–2 assets showing the most concerning trends. "
            "Provide root cause analysis and RUL estimates where applicable."
        )
