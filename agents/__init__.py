from agents.watchkeeper import RealtimeWatchkeeper
from agents.diagnostics import DeepDiagnosticsAgent
from agents.planner import MaintenancePlannerAgent
from agents.compliance import ISMComplianceAgent
from agents.fleet_intel import FleetIntelligenceAgent
from agents.evaluator import ChainEvaluatorAgent


def create_agents(ctx: dict) -> dict:
    """
    Instantiate all 6 agents with shared storage context.
    ctx must contain: ts_store, ev_store, wo_store, cep
    """
    agents = {
        "watchkeeper":   RealtimeWatchkeeper(ctx),
        "diagnostics":   DeepDiagnosticsAgent(ctx),
        "planner":       MaintenancePlannerAgent(ctx),
        "compliance":    ISMComplianceAgent(ctx),
        "fleet_intel":   FleetIntelligenceAgent(ctx),
        "evaluator":     ChainEvaluatorAgent(ctx),
    }
    # Inject the full agents dict into every agent's context so subagent
    # tool handlers can look up and call sibling agents.
    for agent in agents.values():
        agent.ctx["agents"] = agents
    return agents


__all__ = [
    "RealtimeWatchkeeper", "DeepDiagnosticsAgent",
    "MaintenancePlannerAgent", "ISMComplianceAgent",
    "FleetIntelligenceAgent", "ChainEvaluatorAgent",
    "create_agents",
]
