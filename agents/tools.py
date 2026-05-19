"""
Tool registry for all 5 agents.
Each tool is a (schema_dict, handler_function) pair.
Handlers receive (input_dict, ctx) where ctx carries live store references.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from data.inventory import ASSETS, get_asset
from models.events import AlertEvent, AlertSeverity, EventType
from models.maintenance import WorkOrder, WorkOrderStatus, MaintenanceType, SparePart

# Port schedule (hardcoded for demo)
PORT_SCHEDULE = [
    {"port": "Rotterdam", "eta": "2026-05-22", "etd": "2026-05-24", "type": "cargo"},
    {"port": "Hamburg",   "eta": "2026-05-28", "etd": "2026-05-30", "type": "cargo"},
    {"port": "Felixstowe","eta": "2026-06-04", "etd": "2026-06-05", "type": "cargo"},
]

# ISM checklist (simplified per equipment type)
ISM_REQUIREMENTS = {
    "Pump": [
        "Monthly: Check mechanical seal condition and leakage",
        "Monthly: Verify bearing temperature and vibration within limits (ISO 10816)",
        "3-Monthly: Measure pump flow rate vs. rated capacity",
        "Annual: Overhaul per PMS schedule (ISM Code 10.1)",
        "Annual: Update maintenance record in PMS (ISM Code 10.3)",
    ],
    "Compressor": [
        "Weekly: Check oil level and pressure",
        "Monthly: Test safety valves",
        "3-Monthly: Inspect and clean valves",
        "Annual: Full overhaul per OEM schedule (ISM Code 10.1)",
        "Before sailing: Verify starting air pressure ≥25 bar (SOLAS II-1/28)",
    ],
    "Turbocharger": [
        "Weekly: Check lube oil level and pressure during operation",
        "Monthly: Inspect air filter condition; clean if fouled",
        "3-Monthly: Check turbine speed and boost pressure vs. engine curves",
        "Annual: Blades and nozzle ring inspection (class-required > 24,000 hrs)",
        "Annual: Survey report filed with DNV (ISM Code 10.3 / SOLAS II-1)",
    ],
    "Purifier": [
        "Daily: Check bowl speed and motor current",
        "Weekly: Verify sludge discharge cycle timing",
        "Monthly: Check and clean disc stack",
        "3-Monthly: Overhaul bowl and replace gaskets",
        "Annual: Full bowl overhaul with OEM engineer present (ISM Code 10.1)",
    ],
    "Generator": [
        "Daily: Log load, frequency, voltage, exhaust temp",
        "Weekly: Check coolant level, lube oil pressure",
        "Monthly: Test automatic start and load transfer",
        "Annual: Full cylinder head overhaul (ISM Code 10.3)",
        "Annual: Class survey — insulation resistance test (DNV Rules Pt.4 Ch.8)",
    ],
}


# ──────────────────────────────────────────────────────────────────────
# Tool schemas (Anthropic tool_use format)
# ──────────────────────────────────────────────────────────────────────

TOOL_GET_ASSET_HEALTH = {
    "name": "get_asset_health",
    "description": (
        "Returns the latest health metrics and derived telemetry for one shipboard asset. "
        "Includes overall health score (0–100), RUL in days, vibration RMS, anomaly score, "
        "and asset-type-specific efficiency metrics."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string", "description": "Asset ID e.g. PUMP-001, TURBO-001"}
        },
        "required": ["asset_id"],
    },
}

TOOL_GET_TELEMETRY_TREND = {
    "name": "get_telemetry_trend",
    "description": (
        "Returns recent sensor readings for a specific tag on one asset. "
        "Use this to analyse trends, calculate rates of change, or identify step changes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string"},
            "tag":      {"type": "string", "description": "Sensor tag e.g. bearing_temp_c, vibration_x_mms"},
            "limit":    {"type": "integer", "description": "Number of readings to return (max 120)", "default": 30},
        },
        "required": ["asset_id", "tag"],
    },
}

TOOL_GET_FLEET_OVERVIEW = {
    "name": "get_fleet_health_overview",
    "description": "Returns health metrics for all 5 monitored assets simultaneously. Use to identify the worst-performing assets and cross-asset patterns.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

TOOL_GET_RECENT_ALERTS = {
    "name": "get_recent_alerts",
    "description": "Returns the most recent alert events for an asset. Provides context on past anomalies and agent reasoning history.",
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string"},
            "n":        {"type": "integer", "default": 5},
        },
        "required": ["asset_id"],
    },
}

TOOL_GET_MAINTENANCE_HISTORY = {
    "name": "get_maintenance_history",
    "description": "Returns recent completed work orders for an asset. Useful for establishing baseline condition post-maintenance and estimating MTBF.",
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string"},
            "n":        {"type": "integer", "default": 3},
        },
        "required": ["asset_id"],
    },
}

TOOL_RAISE_ALERT = {
    "name": "raise_alert",
    "description": "Create and persist an alert event. Use this when sensor readings breach thresholds or anomaly patterns require engineering attention.",
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id":           {"type": "string"},
            "severity":           {"type": "string", "enum": ["Info", "Warning", "Alarm", "Critical"]},
            "title":              {"type": "string", "description": "Short alert title (< 80 chars)"},
            "description":        {"type": "string", "description": "Detailed description of the anomaly"},
            "recommended_action": {"type": "string", "description": "Recommended next action for the engineer"},
            "tag":                {"type": "string", "description": "Primary sensor tag that triggered the alert"},
            "observed_value":     {"type": "number"},
            "threshold_value":    {"type": "number"},
            "unit":               {"type": "string"},
        },
        "required": ["asset_id", "severity", "title", "description", "recommended_action"],
    },
}

TOOL_CREATE_WORK_ORDER = {
    "name": "create_work_order",
    "description": "Create a draft condition-based maintenance work order. It will be held for Chief Engineer approval before scheduling.",
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id":              {"type": "string"},
            "title":                 {"type": "string"},
            "description":           {"type": "string"},
            "ai_rationale":          {"type": "string", "description": "Your reasoning for raising this work order"},
            "priority":              {"type": "integer", "description": "1=Critical 2=High 3=Medium 4=Low 5=Routine"},
            "maintenance_type":      {"type": "string", "enum": ["Condition-Based", "Planned", "Corrective", "Emergency"]},
            "requires_port":         {"type": "boolean"},
            "recommended_window":    {"type": "string", "description": "e.g. Next port call — Rotterdam 2026-05-22"},
            "estimated_hours":       {"type": "number"},
            "estimated_cost_usd":    {"type": "number"},
            "requires_class_surveyor": {"type": "boolean", "default": False},
        },
        "required": ["asset_id", "title", "description", "ai_rationale", "priority", "maintenance_type"],
    },
}

TOOL_GET_PORT_SCHEDULE = {
    "name": "get_port_schedule",
    "description": "Returns the vessel's upcoming port call schedule. Use to recommend maintenance windows that align with port availability.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

TOOL_GET_ISM_REQUIREMENTS = {
    "name": "get_ism_requirements",
    "description": "Returns the ISM Code maintenance requirements for a given equipment type.",
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_type": {"type": "string", "enum": ["Pump", "Compressor", "Turbocharger", "Purifier", "Generator"]}
        },
        "required": ["asset_type"],
    },
}

TOOL_GET_FLEET_MTBF = {
    "name": "get_fleet_mtbf_summary",
    "description": "Returns mean-time-between-failure statistics derived from historical maintenance records across all fleet assets.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
}

TOOL_GET_HF_ANALYSIS = {
    "name": "get_hf_analysis",
    "description": (
        "Runs the high-frequency (10 Hz) ML analysis pipeline on an asset and returns "
        "structured results including: anomaly detection score (Isolation Forest), "
        "fault classification (bearing_wear / cavitation / imbalance / misalignment / "
        "looseness / seal_leak / fouling / normal) with probabilities, RUL estimate from "
        "vibration trend, and key signal features (kurtosis, crest factor, dominant "
        "frequency, spectral analysis). Use this FIRST when diagnosing any asset — it "
        "provides ML-grounded evidence to augment CEP sensor data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {
                "type": "string",
                "description": "Asset ID e.g. PUMP-001, TURBO-001",
            },
            "duration_s": {
                "type": "integer",
                "description": "HF window duration in seconds to analyse (default 120, max 600)",
                "default": 120,
            },
        },
        "required": ["asset_id"],
    },
}

# ── Subagent tools — Watchkeeper calls these to orchestrate the chain ─────────

TOOL_CALL_DIAGNOSTICS = {
    "name": "call_deep_diagnostics",
    "description": (
        "Escalate to the Deep Diagnostics agent for full root cause analysis, ML anomaly "
        "detection, and RUL estimation. Call this AFTER confirming the alarm is real. "
        "Returns a detailed diagnostic report including fault class, severity, and "
        "recommended action. Do NOT call if the alarm appears to be a sensor glitch."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string", "description": "Asset ID to investigate"},
            "reason":   {"type": "string", "description": "Your watchkeeper findings that justify escalation (2–3 sentences)"},
            "severity": {"type": "string", "enum": ["medium", "high", "critical"],
                         "description": "Your assessed severity based on breach level and cross-correlation"},
        },
        "required": ["asset_id", "reason", "severity"],
    },
}

TOOL_CALL_PLANNER = {
    "name": "call_maintenance_planner",
    "description": (
        "Call the Maintenance Planner agent to create a draft work order based on "
        "the diagnostic findings. Call this AFTER receiving the diagnostic report. "
        "Returns the created work order ID and scheduling details. "
        "Always call this unless diagnostics found no fault (normal/healthy state)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id":           {"type": "string"},
            "diagnostic_summary": {"type": "string",
                                   "description": "Key findings from diagnostics (fault class, RUL, recommended action)"},
        },
        "required": ["asset_id", "diagnostic_summary"],
    },
}

TOOL_CALL_COMPLIANCE = {
    "name": "call_compliance_check",
    "description": (
        "Call the ISM Compliance agent to assess regulatory obligations. "
        "Use for SOLAS-critical assets (COMP-001 starting air, AUXGEN-001 generator) "
        "or when a compliance code was flagged in the alarm. Returns compliance status "
        "and any non-conformities found."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string"},
            "context":  {"type": "string",
                         "description": "Alarm context including compliance code (e.g. SOLAS-II-1/28) and metric values"},
        },
        "required": ["asset_id", "context"],
    },
}

TOOL_CALL_FLEET_INTEL = {
    "name": "call_fleet_intelligence",
    "description": (
        "Call the Fleet Intelligence agent to update the fleet-wide advisory report. "
        "Use for SOLAS/ISM-critical incidents (Tier 3). Returns an executive summary "
        "with fleet risk ranking, cost outlook, and strategic recommendations."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_id": {"type": "string", "description": "Primary asset triggering the fleet review"},
        },
        "required": ["asset_id"],
    },
}

TOOL_CALL_EVALUATOR = {
    "name": "call_chain_evaluator",
    "description": (
        "Call the Chain Evaluator agent to score the quality of this entire incident response. "
        "ALWAYS call this as the LAST step of every chain, after all other agents have completed. "
        "Returns a structured quality assessment with scores per agent and an overall verdict."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "The incident ID for this chain"},
            "chain_summary": {"type": "string",
                              "description": "Your 1–2 sentence summary of what the chain found and decided"},
        },
        "required": ["incident_id", "chain_summary"],
    },
}

TOOL_GET_INCIDENT_REPORT = {
    "name": "get_incident_chain_report",
    "description": (
        "Retrieves the complete agent chain outputs for a specific incident. "
        "Returns all agent step outputs, tool call counts, timing, and results. "
        "Used by the Chain Evaluator to assess chain quality."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "Incident ID e.g. INC-2026-001"},
        },
        "required": ["incident_id"],
    },
}

TOOL_KB_RETRIEVE = {
    "name": "kb_retrieve",
    "description": (
        "Search the on-board maritime knowledge base for relevant technical guidance. "
        "Contains OEM failure mode patterns, maintenance intervals, ISO/IACS standards, "
        "SOLAS/ISM regulatory requirements, and diagnostic troubleshooting guides. "
        "Use this to cite specific standards, identify failure mechanisms, or confirm "
        "regulatory obligations before raising alerts or work orders."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Technical search query e.g. 'turbocharger bearing vibration sub-synchronous' or 'SOLAS starting air requirements'",
            },
            "asset_type": {
                "type": "string",
                "description": "Optional: filter by asset type",
                "enum": ["pump", "compressor", "turbocharger", "purifier", "generator"],
            },
            "category": {
                "type": "string",
                "description": "Optional: filter by knowledge category",
                "enum": ["failure_modes", "maintenance_intervals", "regulations", "iacs_standards", "troubleshooting"],
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default 3, max 5)",
                "default": 3,
            },
        },
        "required": ["query"],
    },
}


# ──────────────────────────────────────────────────────────────────────
# Tool dispatcher
# ──────────────────────────────────────────────────────────────────────

def execute_tool(name: str, tool_input: dict, ctx: dict) -> str:
    ts_store  = ctx["ts_store"]
    ev_store  = ctx["ev_store"]
    wo_store  = ctx["wo_store"]
    cep       = ctx["cep"]
    agent_name = ctx.get("agent_name", "unknown_agent")

    if name == "get_asset_health":
        asset_id = tool_input["asset_id"]
        derived = cep.latest_derived.get(asset_id)
        asset   = ASSETS.get(asset_id)
        if not derived or not asset:
            return json.dumps({"error": f"No data for {asset_id}"})
        return json.dumps({
            "asset_id":          asset_id,
            "display_name":      asset.display_name,
            "asset_type":        asset.asset_type.value,
            "running_hours":     asset.running_hours,
            "last_maintenance":  asset.last_maintenance.isoformat() if asset.last_maintenance else None,
            "next_scheduled_pm": asset.next_scheduled_maintenance.isoformat() if asset.next_scheduled_maintenance else None,
            "health_score":      derived.overall_health_score,
            "health_tier":       derived.health_tier,
            "rul_days":          derived.rul_days,
            "vibration_rms_mms": derived.vibration_rms_mms,
            "anomaly_score":     derived.anomaly_score,
            "vibration_trend_slope_mms_per_hour": derived.vibration_trend_slope,
            "pump_efficiency_pct":       derived.pump_efficiency_pct,
            "bearing_wear_index":        derived.bearing_wear_index,
            "differential_pressure_bar": derived.differential_pressure_bar,
            "compression_ratio":         derived.compression_ratio,
            "volumetric_efficiency_pct": derived.volumetric_efficiency_pct,
            "turbo_efficiency_pct":      derived.turbo_efficiency_pct,
            "exhaust_delta_temp_c":      derived.exhaust_delta_temp_c,
            "surge_margin_pct":          derived.surge_margin_pct,
            "bowl_speed_deviation_pct":  derived.bowl_speed_deviation_pct,
            "separation_efficiency_pct": derived.separation_efficiency_pct,
            "load_factor_pct":           derived.load_factor_pct,
            "frequency_deviation_hz":    derived.frequency_deviation_hz,
            "specific_fuel_consumption": derived.specific_fuel_consumption,
        }, default=str)

    elif name == "get_telemetry_trend":
        asset_id = tool_input["asset_id"]
        tag      = tool_input["tag"]
        limit    = min(tool_input.get("limit", 30), 120)
        rows     = ts_store.get_tag_history(asset_id, tag, limit=limit)
        if not rows:
            return json.dumps({"error": f"No data for {asset_id}/{tag}"})
        values = [r["value"] for r in rows]
        import statistics
        return json.dumps({
            "asset_id": asset_id, "tag": tag,
            "count": len(values),
            "latest": values[-1] if values else None,
            "mean":   round(statistics.mean(values), 3),
            "min":    round(min(values), 3),
            "max":    round(max(values), 3),
            "stdev":  round(statistics.stdev(values), 3) if len(values) > 1 else 0,
            "trend":  "rising" if len(values) > 5 and values[-1] > values[-5] else
                      "falling" if len(values) > 5 and values[-1] < values[-5] else "stable",
            "recent_readings": rows[-10:],
        })

    elif name == "get_fleet_health_overview":
        overview = []
        for asset_id, asset in ASSETS.items():
            derived = cep.latest_derived.get(asset_id)
            overview.append({
                "asset_id":    asset_id,
                "name":        asset.display_name,
                "type":        asset.asset_type.value,
                "health_score": derived.overall_health_score if derived else None,
                "health_tier":  derived.health_tier if derived else "Unknown",
                "rul_days":     derived.rul_days if derived else None,
                "anomaly_score": derived.anomaly_score if derived else None,
                "next_pm":     asset.next_scheduled_maintenance.isoformat() if asset.next_scheduled_maintenance else None,
            })
        overview.sort(key=lambda x: (x["health_score"] or 100))
        return json.dumps({"vessel": "MV-Callisto", "assets": overview})

    elif name == "get_recent_alerts":
        asset_id = tool_input["asset_id"]
        n = tool_input.get("n", 5)
        events = ev_store.get_context_for_agent(asset_id, n)
        return json.dumps({"asset_id": asset_id, "recent_alerts": events})

    elif name == "get_maintenance_history":
        asset_id = tool_input["asset_id"]
        n = tool_input.get("n", 3)
        history = wo_store.get_context_for_agent(asset_id, n)
        return json.dumps({"asset_id": asset_id, "maintenance_history": history})

    elif name == "raise_alert":
        event = AlertEvent(
            event_id=str(uuid.uuid4()),
            asset_id=tool_input["asset_id"],
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.AGENT_ALERT,
            severity=AlertSeverity(tool_input["severity"]),
            title=tool_input["title"],
            description=tool_input["description"],
            agent_name=agent_name,
            agent_reasoning=tool_input["description"],
            recommended_action=tool_input["recommended_action"],
            tag=tool_input.get("tag"),
            observed_value=tool_input.get("observed_value"),
            threshold_value=tool_input.get("threshold_value"),
            unit=tool_input.get("unit"),
        )
        ev_store.save_event(event)
        return json.dumps({"status": "alert_raised", "event_id": event.event_id,
                           "severity": event.severity.value, "title": event.title})

    elif name == "create_work_order":
        wo_id = f"WO-{datetime.now().year}-{str(uuid.uuid4())[:4].upper()}"
        wo = WorkOrder(
            work_order_id=wo_id,
            asset_id=tool_input["asset_id"],
            maintenance_type=MaintenanceType(tool_input["maintenance_type"]),
            status=WorkOrderStatus.DRAFT,
            priority=tool_input["priority"],
            title=tool_input["title"],
            description=tool_input["description"],
            ai_rationale=tool_input["ai_rationale"],
            created_at=datetime.now(timezone.utc),
            recommended_window=tool_input.get("recommended_window"),
            estimated_duration_hours=tool_input.get("estimated_hours", 4.0),
            requires_port=tool_input.get("requires_port", True),
            requires_class_surveyor=tool_input.get("requires_class_surveyor", False),
            estimated_cost_usd=tool_input.get("estimated_cost_usd"),
        )
        wo_store.save_work_order(wo)
        return json.dumps({"status": "work_order_created", "work_order_id": wo_id,
                           "awaiting": "Chief Engineer approval"})

    elif name == "get_port_schedule":
        return json.dumps({"vessel": "MV-Callisto", "port_calls": PORT_SCHEDULE})

    elif name == "get_ism_requirements":
        asset_type = tool_input["asset_type"]
        return json.dumps({
            "asset_type": asset_type,
            "requirements": ISM_REQUIREMENTS.get(asset_type, []),
            "reference": "ISM Code Section 10 — Maintenance of the Ship and Equipment",
        })

    elif name == "get_fleet_mtbf_summary":
        from data.maintenance_history import MAINTENANCE_HISTORY
        from collections import defaultdict
        by_type: dict[str, list] = defaultdict(list)
        for wo in MAINTENANCE_HISTORY:
            asset = ASSETS.get(wo.asset_id)
            if asset and wo.completed_at and wo.started_at:
                by_type[asset.asset_type.value].append({
                    "asset_id": wo.asset_id,
                    "running_hours_at_failure": asset.running_hours,
                    "actual_cost_usd": wo.actual_cost_usd,
                    "maintenance_type": wo.maintenance_type.value,
                })
        return json.dumps({"mtbf_by_type": dict(by_type),
                           "note": "Based on maintenance history since commissioning"})

    elif name == "kb_retrieve":
        from kb.retriever import kb_retrieve_formatted
        query      = tool_input["query"]
        asset_type = tool_input.get("asset_type")
        category   = tool_input.get("category")
        top_k      = min(tool_input.get("top_k", 3), 5)
        return kb_retrieve_formatted(query, asset_type=asset_type, category=category, top_k=top_k)

    elif name == "get_hf_analysis":
        asset_id   = tool_input["asset_id"]
        duration_s = min(int(tool_input.get("duration_s", 120)), 600)
        incident_id = ctx.get("incident_id")
        try:
            from ml.pipeline import MLPipeline
            from storage.hf_store import hf_store
            import pipeline.incident_store as _inc_store

            # Mark ml_analysis step as running in incident store
            if incident_id:
                _inc_store.start_step(incident_id, "ml_analysis")

            # Get ML pipeline from context (injected by app.py) or create one on demand
            ml_pipeline = ctx.get("ml_pipeline")
            if ml_pipeline is None:
                ml_pipeline = MLPipeline(hf_store)

            # Get asset type from inventory (ASSETS imported at module level)
            asset = ASSETS.get(asset_id)
            asset_type = asset.asset_type.value if asset else "Unknown"

            # Get CEP health + RUL for blending
            cep_health = None
            cep_rul    = None
            derived = cep.latest_derived.get(asset_id)
            if derived:
                cep_health = derived.overall_health_score
                cep_rul    = derived.rul_days

            result = ml_pipeline.analyze(
                asset_id=asset_id,
                asset_type=asset_type,
                duration_s=duration_s,
                cep_health=cep_health,
                cep_rul=cep_rul,
            )

            # Update incident store ml_analysis step
            if incident_id:
                _inc_store.complete_ml_analysis(incident_id, result, tool_calls=1)

            return json.dumps(result.to_agent_dict(), default=str)

        except Exception as e:
            if incident_id:
                try:
                    import pipeline.incident_store as _inc_store2
                    _inc_store2.complete_ml_analysis(incident_id, None, tool_calls=0)
                except Exception:
                    pass
            return json.dumps({"error": f"HF analysis failed: {str(e)}", "asset_id": asset_id})

    # ── Subagent orchestration tools ──────────────────────────────────────────

    elif name == "call_deep_diagnostics":
        import pipeline.incident_store as _inc_store
        agents     = ctx.get("agents", {})
        incident_id = ctx.get("incident_id")
        asset_id   = tool_input["asset_id"]
        reason     = tool_input.get("reason", "")
        severity   = tool_input.get("severity", "medium")

        diag_agent = agents.get("diagnostics")
        if diag_agent is None:
            return json.dumps({"error": "DiagnosticsAgent not available in context"})

        # Propagate incident_id into diagnostics agent context
        diag_agent.ctx["incident_id"] = incident_id
        diag_agent.ctx["ml_pipeline"] = ctx.get("ml_pipeline")

        if incident_id:
            _inc_store.start_step(incident_id, "diagnostics")

        trigger = {"asset_id": asset_id, "reason": reason, "severity": severity,
                   "incident_id": incident_id}
        try:
            result = diag_agent.run(trigger)
            summary = result.summary[:200]
            if incident_id:
                _inc_store.complete_diagnostics(
                    incident_id, summary,
                    tool_calls=len(result.actions_taken),
                    full_output=result.full_reasoning,
                )
            return json.dumps({
                "status": "diagnostics_complete",
                "asset_id": asset_id,
                "summary": summary,
                "full_report": result.full_reasoning[:4000],
                "tool_calls": len(result.actions_taken),
            })
        except Exception as e:
            if incident_id:
                _inc_store.complete_diagnostics(incident_id, f"Error: {e}", tool_calls=0)
            return json.dumps({"error": f"Diagnostics failed: {str(e)}", "asset_id": asset_id})

    elif name == "call_maintenance_planner":
        import pipeline.incident_store as _inc_store
        agents     = ctx.get("agents", {})
        incident_id = ctx.get("incident_id")
        asset_id   = tool_input["asset_id"]
        diag_summary = tool_input.get("diagnostic_summary", "")

        planner_agent = agents.get("planner")
        if planner_agent is None:
            return json.dumps({"error": "PlannerAgent not available in context"})

        planner_agent.ctx["incident_id"] = incident_id

        if incident_id:
            _inc_store.start_step(incident_id, "planner")

        trigger = {"asset_id": asset_id, "diagnostic_summary": diag_summary,
                   "incident_id": incident_id}
        try:
            result = planner_agent.run(trigger)
            summary = result.summary[:200]

            # Extract work order ID from actions
            wo_id = None
            for action in result.actions_taken:
                if action.get("tool") == "create_work_order":
                    try:
                        out = json.loads(action.get("output", "{}"))
                        wo_id = out.get("work_order_id")
                    except Exception:
                        pass
                    if wo_id:
                        break

            if incident_id:
                _inc_store.complete_planner(
                    incident_id, summary, wo_id,
                    tool_calls=len(result.actions_taken),
                    full_output=result.full_reasoning,
                )
            return json.dumps({
                "status": "planning_complete",
                "asset_id": asset_id,
                "work_order_id": wo_id,
                "summary": summary,
                "full_report": result.full_reasoning[:4000],
            })
        except Exception as e:
            if incident_id:
                _inc_store.complete_planner(incident_id, f"Error: {e}", None, tool_calls=0)
            return json.dumps({"error": f"Planner failed: {str(e)}", "asset_id": asset_id})

    elif name == "call_compliance_check":
        import pipeline.incident_store as _inc_store
        agents     = ctx.get("agents", {})
        incident_id = ctx.get("incident_id")
        asset_id   = tool_input["asset_id"]
        context_str = tool_input.get("context", "")

        compliance_agent = agents.get("compliance")
        if compliance_agent is None:
            return json.dumps({"error": "ComplianceAgent not available in context"})

        compliance_agent.ctx["incident_id"] = incident_id

        if incident_id:
            _inc_store.start_step(incident_id, "compliance")

        trigger = {"asset_id": asset_id, "context": context_str,
                   "incident_id": incident_id}
        try:
            result = compliance_agent.run(trigger)
            summary = result.summary[:200]

            # Extract compliance status from full reasoning
            import re as _re
            status = "UNKNOWN"
            for keyword in ("COMPLIANT", "MAJOR NC", "MINOR NC"):
                if keyword in result.full_reasoning.upper():
                    status = keyword
                    break

            if incident_id:
                _inc_store.complete_compliance(
                    incident_id, summary, status,
                    tool_calls=len(result.actions_taken),
                    full_output=result.full_reasoning,
                )
            return json.dumps({
                "status": "compliance_complete",
                "asset_id": asset_id,
                "compliance_status": status,
                "summary": summary,
                "full_report": result.full_reasoning[:4000],
            })
        except Exception as e:
            if incident_id:
                _inc_store.complete_compliance(incident_id, f"Error: {e}", "ERROR", tool_calls=0)
            return json.dumps({"error": f"Compliance check failed: {str(e)}", "asset_id": asset_id})

    elif name == "call_fleet_intelligence":
        import pipeline.incident_store as _inc_store
        agents     = ctx.get("agents", {})
        incident_id = ctx.get("incident_id")
        asset_id   = tool_input["asset_id"]

        fleet_agent = agents.get("fleet_intel")
        if fleet_agent is None:
            return json.dumps({"error": "FleetIntelAgent not available in context"})

        fleet_agent.ctx["incident_id"] = incident_id

        if incident_id:
            _inc_store.start_step(incident_id, "fleet_intel")

        trigger = {"asset_id": asset_id, "incident_id": incident_id}
        try:
            result = fleet_agent.run(trigger)
            advisory = result.summary[:200]

            if incident_id:
                _inc_store.complete_fleet_intel(
                    incident_id, advisory,
                    tool_calls=len(result.actions_taken),
                    full_output=result.full_reasoning,
                )
            return json.dumps({
                "status": "fleet_intel_complete",
                "asset_id": asset_id,
                "advisory": advisory,
                "full_report": result.full_reasoning[:4000],
            })
        except Exception as e:
            if incident_id:
                _inc_store.complete_fleet_intel(incident_id, f"Error: {e}", tool_calls=0)
            return json.dumps({"error": f"Fleet intel failed: {str(e)}", "asset_id": asset_id})

    elif name == "call_chain_evaluator":
        import pipeline.incident_store as _inc_store
        agents      = ctx.get("agents", {})
        incident_id = tool_input.get("incident_id") or ctx.get("incident_id")
        chain_summary = tool_input.get("chain_summary", "")

        evaluator_agent = agents.get("evaluator")
        if evaluator_agent is None:
            return json.dumps({"error": "EvaluatorAgent not available in context"})

        evaluator_agent.ctx["incident_id"] = incident_id

        if incident_id:
            _inc_store.start_step(incident_id, "evaluator")

        trigger = {"incident_id": incident_id, "chain_summary": chain_summary,
                   "asset_id": ctx.get("asset_id", "unknown")}
        try:
            result = evaluator_agent.run(trigger)
            summary = result.summary[:200]

            # Extract overall score from reasoning — look for "Overall Score: N/100"
            import re as _re
            score = 75  # default
            m = _re.search(r"Overall Score[:\s]+(\d+)\s*/\s*100", result.full_reasoning, _re.IGNORECASE)
            if m:
                score = int(m.group(1))

            if incident_id:
                _inc_store.complete_evaluator(
                    incident_id, summary, score,
                    tool_calls=len(result.actions_taken),
                    full_output=result.full_reasoning,
                )
            return json.dumps({
                "status": "evaluation_complete",
                "incident_id": incident_id,
                "overall_score": score,
                "summary": summary,
                "full_report": result.full_reasoning[:4000],
            })
        except Exception as e:
            if incident_id:
                _inc_store.complete_evaluator(incident_id, f"Error: {e}", 0, tool_calls=0)
            return json.dumps({"error": f"Evaluator failed: {str(e)}", "incident_id": incident_id})

    elif name == "get_incident_chain_report":
        import pipeline.incident_store as _inc_store
        incident_id = tool_input["incident_id"]
        inc = _inc_store.get_by_id(incident_id)
        if not inc:
            return json.dumps({"error": f"Incident {incident_id} not found"})

        steps_data = {}
        for step_name, step in inc.steps.items():
            steps_data[step_name] = {
                "status":      step.status,
                "label":       step.label,
                "tool_calls":  step.tool_calls,
                "duration_s":  round(step.duration_s, 1),
                "summary":     step.summary,
                "full_output": step.full_output[:3000] if step.full_output else "",
            }

        return json.dumps({
            "incident_id":   inc.incident_id,
            "asset_id":      inc.asset_id,
            "metric":        inc.metric,
            "tier":          inc.tier,
            "tier_label":    inc.tier_label,
            "triggered_at":  inc.triggered_at.isoformat(),
            "trigger_value": inc.trigger_value,
            "trigger_unit":  inc.trigger_unit,
            "status":        inc.status,
            "wo_id":         inc.wo_id,
            "compliance_status": inc.compliance_status,
            "fleet_advisory": inc.fleet_advisory,
            "evaluator_score": inc.evaluator_score,
            "steps":         steps_data,
        }, default=str)

    return json.dumps({"error": f"Unknown tool: {name}"})
