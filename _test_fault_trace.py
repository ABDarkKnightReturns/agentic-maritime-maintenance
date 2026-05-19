"""Diagnose why PURIF-001 and AUXGEN-001 faults don't trigger alarms."""
import sys, time
sys.path.insert(0, r'C:\Users\abhis\maritime-maintenance-demo')

from simulator import create_fleet
from pipeline import broker, DataHarmonizer, CEPEngine
from pipeline.alarm_manager import alarm_manager
from storage.database import initialise_schema
from data.thresholds import ASSET_THRESHOLDS

initialise_schema()
harmonizer = DataHarmonizer()
cep = CEPEngine()
harmonizer.start()
cep.start()

fleet = create_fleet()

# ── Test what tags each simulator emits ──────────────────────────────────────
print("=== Simulator output tags ===")
for asset_id, sim in fleet.items():
    _, msgs = sim.tick()
    tags = [m.tag for m in msgs if m.tag]
    print(f"  {asset_id}: {tags}")

# ── Test what happens to AUXGEN with fault ────────────────────────────────────
print("\n=== AUXGEN-001 fault test ===")
fleet["AUXGEN-001"].inject_fault(0.5)
print(f"Simulator health after fault: {fleet['AUXGEN-001'].health:.2f}")

for _ in range(30):
    for asset_id, sim in fleet.items():
        _, msgs = sim.tick()
        broker.publish_many(msgs)
    time.sleep(0.05)
time.sleep(1.5)

m = cep.latest_derived.get("AUXGEN-001")
if m:
    print(f"  health_score:         {m.overall_health_score}")
    print(f"  vibration_rms_mms:    {m.vibration_rms_mms}")
    print(f"  frequency_deviation:  {m.frequency_deviation_hz}")
    print(f"  load_factor_pct:      {m.load_factor_pct}")
    print(f"  anomaly_score:        {m.anomaly_score}")
else:
    print("  No derived metrics yet")

# ── Test PURIF-001 fault ──────────────────────────────────────────────────────
print("\n=== PURIF-001 fault test ===")
fleet["PURIF-001"].inject_fault(0.5)
print(f"Simulator health after fault: {fleet['PURIF-001'].health:.2f}")

for _ in range(30):
    for asset_id, sim in fleet.items():
        _, msgs = sim.tick()
        broker.publish_many(msgs)
    time.sleep(0.05)
time.sleep(1.5)

m = cep.latest_derived.get("PURIF-001")
if m:
    print(f"  health_score:              {m.overall_health_score}")
    print(f"  vibration_rms_mms:         {m.vibration_rms_mms}")
    print(f"  bowl_speed_deviation_pct:  {m.bowl_speed_deviation_pct}")
    print(f"  separation_efficiency_pct: {m.separation_efficiency_pct}")
    print(f"  anomaly_score:             {m.anomaly_score}")

# ── Check thresholds for each metric ─────────────────────────────────────────
print("\n=== Threshold checks for PURIF-001 ===")
thresholds = ASSET_THRESHOLDS.get("PURIF-001", {})
for metric, threshold in thresholds.items():
    val = getattr(m, metric, None)
    level = threshold.check(val) if val is not None else "NO DATA"
    print(f"  {metric}: value={val}  → {level}  "
          f"(warn={threshold.warning} alarm={threshold.alarm} dir={threshold.direction})")

print("\n=== Threshold checks for AUXGEN-001 ===")
ma = cep.latest_derived.get("AUXGEN-001")
thresholds_g = ASSET_THRESHOLDS.get("AUXGEN-001", {})
for metric, threshold in thresholds_g.items():
    val = getattr(ma, metric, None)
    level = threshold.check(val) if val is not None else "NO DATA"
    print(f"  {metric}: value={val}  → {level}  "
          f"(warn={threshold.warning} alarm={threshold.alarm} dir={threshold.direction})")

# ── Check alarm manager state ─────────────────────────────────────────────────
print(f"\n=== Active alarms: {len(alarm_manager.get_active_alarms())} ===")
for a in alarm_manager.get_active_alarms():
    print(f"  [{a.level}] {a.asset_id}.{a.metric} = {a.last_value:.2f} {a.unit}")
