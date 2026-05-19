from simulator.pump_simulator import PumpSimulator
from simulator.compressor_simulator import CompressorSimulator
from simulator.turbo_simulator import TurboSimulator
from simulator.purifier_simulator import PurifierSimulator
from simulator.generator_simulator import GeneratorSimulator

# Registry: asset_id -> simulator instance
def create_fleet() -> dict:
    return {
        "PUMP-001":    PumpSimulator("PUMP-001", "Pump"),
        "COMP-001":    CompressorSimulator("COMP-001", "Compressor"),
        "TURBO-001":   TurboSimulator("TURBO-001", "Turbocharger"),
        "PURIF-001":   PurifierSimulator("PURIF-001", "Purifier"),
        "AUXGEN-001":  GeneratorSimulator("AUXGEN-001", "Generator"),
    }

__all__ = [
    "PumpSimulator", "CompressorSimulator", "TurboSimulator",
    "PurifierSimulator", "GeneratorSimulator", "create_fleet",
]
