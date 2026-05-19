import sys, time
sys.path.insert(0, r'C:\Users\abhis\maritime-maintenance-demo')

from simulator import create_fleet
from pipeline import broker, DataHarmonizer, CEPEngine

harmonizer = DataHarmonizer()
cep = CEPEngine()
harmonizer.start()
cep.start()

fleet = create_fleet()
for tick in range(5):
    for asset_id, sim in fleet.items():
        snapshot, messages = sim.tick()
        broker.publish_many(messages)
    time.sleep(0.12)

time.sleep(1.5)

print("\nBroker stats:", broker.stats)
print("Harmonizer stats:", harmonizer.stats)
print()

header = f"{'Asset':<12} {'Health':>7} {'RUL(d)':>8} {'VibRMS':>8} {'Anomaly':>9}"
print(header)
print("-" * len(header))
for asset_id, m in cep.latest_derived.items():
    rul = m.rul_days if m.rul_days is not None else -1
    vib = m.vibration_rms_mms if m.vibration_rms_mms is not None else 0
    print(f"{asset_id:<12} {m.overall_health_score:>7.1f} {rul:>8.1f} {vib:>8.3f} {m.anomaly_score:>9.3f}")

print()
pump = cep.latest_derived.get("PUMP-001")
if pump:
    print("PUMP-001 derived detail:")
    print(f"  pump_efficiency_pct  = {pump.pump_efficiency_pct}")
    print(f"  bearing_wear_index   = {pump.bearing_wear_index}")
    print(f"  differential_press   = {pump.differential_pressure_bar} bar")
    print(f"  health_tier          = {pump.health_tier}")
    print(f"  UNS topic            = Maersk/MV-Eindhoven/EngineRoom/Pump/PUMP-001/Derived/health_snapshot")
