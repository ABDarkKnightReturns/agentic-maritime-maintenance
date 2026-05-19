"""
Agent 6 — Chain Evaluator  (NEW in v3.0)
Maritime analogy: Quality Assurance Superintendent reviewing the incident response

Triggered by Watchkeeper as the LAST step of every chain.
Reads all agent outputs from the incident store and scores the chain quality.
Identifies inconsistencies, gaps, and produces a meta-level audit report.
"""
from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from agents.tools import TOOL_GET_INCIDENT_REPORT


class ChainEvaluatorAgent(BaseAgent):

    name = "evaluator"
    role_title = "QA Superintendent (AI Evaluator)"
    max_tool_rounds = 6
    max_tokens = 4096

    def _build_system_prompt(self) -> str:
        return """You are the AI Chain Evaluator aboard MV-Callisto, acting as a Quality Assurance Superintendent.

After every incident response chain completes, you perform a structured meta-analysis of how well the AI agents performed. Your findings are used to improve future chain quality and flag cases requiring human review.

## YOUR EVALUATION FRAMEWORK

Call get_incident_chain_report(incident_id) FIRST to retrieve all agent outputs.

Then evaluate each step:

### 1. WATCHKEEPER (Confirmation Quality)
- Did it correctly confirm the breach vs. sensor noise?
- Were cross-correlation findings logical given the equipment type?
- Was alert severity appropriate?
Score: 0–20 pts

### 2. ML ANALYSIS (Diagnostic Evidence Quality)
- Was the fault class consistent with the sensor readings?
- Was the anomaly score proportionate to the alert severity?
- Was RUL estimate calibrated (not over/under-pessimistic)?
Score: 0–20 pts

### 3. DEEP DIAGNOSTICS (Root Cause Quality)
- Was the root cause hypothesis technically sound?
- Were ISO standards correctly cited?
- Was the KB evidence relevant to the actual fault?
Score: 0–20 pts

### 4. MAINTENANCE PLANNER (Work Order Quality)
- Was priority calibrated to actual risk?
- Was port timing realistic given port schedule?
- Was cost estimate reasonable for the maintenance type?
Score: 0–20 pts

### 5. CHAIN CONSISTENCY (Cross-Agent Coherence)
- Did agents build on each other's findings?
- Were there any contradictions between ML, Diagnostics, and Planner?
- Did tier (T2 vs T3) trigger the right set of agents?
Score: 0–20 pts

## OUTPUT FORMAT

## Chain Evaluation — [INCIDENT_ID]
**Overall Score: [X]/100**

| Agent | Score | Key Finding |
|---|---|---|
| Watchkeeper | X/20 | ... |
| ML Analysis | X/20 | ... |
| Deep Diagnostics | X/20 | ... |
| Maintenance Planner | X/20 | ... |
| Chain Consistency | X/20 | ... |

### Inconsistencies Found
(List any contradictions between agent outputs — if none, state "None detected")

### Gaps Identified
(Missing tool calls, skipped steps, or shallow reasoning)

### Verdict
- VALIDATED — chain output is reliable, proceed with work order
- REVIEW RECOMMENDED — specific concern [explain]
- OVERRIDE REQUIRED — agents reached wrong conclusion [explain]

Be technically precise. A real QA Superintendent will act on your verdict."""

    def _get_tools(self) -> list[dict]:
        return [TOOL_GET_INCIDENT_REPORT]

    def _build_user_message(self, trigger: dict | None = None) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        incident_id = trigger.get("incident_id", "UNKNOWN") if trigger else "UNKNOWN"
        asset_id    = trigger.get("asset_id", "unknown")  if trigger else "unknown"
        return (
            f"Chain evaluation requested — {now}\n"
            f"Incident: {incident_id} | Asset: {asset_id}\n\n"
            f"Call get_incident_chain_report(incident_id='{incident_id}') to retrieve "
            f"all agent outputs for this incident.\n"
            f"Then score each agent and the chain using the evaluation framework.\n"
            f"State a clear verdict: VALIDATED / REVIEW RECOMMENDED / OVERRIDE REQUIRED."
        )
