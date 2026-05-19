from agents.watchkeeper import RealtimeWatchkeeper
from agents.diagnostics import DeepDiagnosticsAgent
from agents.planner import MaintenancePlannerAgent
from agents.compliance import ISMComplianceAgent
from agents.fleet_intel import FleetIntelligenceAgent


def create_agents(ctx: dict) -> dict:
    """
    Instantiate all 5 agents with shared storage context.
    ctx must contain: ts_store, ev_store, wo_store, cep
    """
    return {
        "watchkeeper":   RealtimeWatchkeeper(ctx),
        "diagnostics":   DeepDiagnosticsAgent(ctx),
        "planner":       MaintenancePlannerAgent(ctx),
        "compliance":    ISMComplianceAgent(ctx),
        "fleet_intel":   FleetIntelligenceAgent(ctx),
    }


__all__ = [
    "RealtimeWatchkeeper", "DeepDiagnosticsAgent",
    "MaintenancePlannerAgent", "ISMComplianceAgent",
    "FleetIntelligenceAgent", "create_agents",
]
