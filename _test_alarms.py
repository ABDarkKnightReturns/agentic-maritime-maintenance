"""Test alarm manager threshold detection and lifecycle."""
import sys, time
sys.path.insert(0, r'C:\Users\abhis\maritime-maintenance-demo')

from pipeline.alarm_manager import alarm_manager, AlarmManager
from models.derived import DerivedMetrics
from datetime import datetime, timezone

def make_metrics(asset_id, **kwargs):
    base = dict(asset_id=asset_id, timestamp=datetime.now(timezone.utc),
                overall_health_score=80.0, vibration_rms_mms=2.0,
                anomaly_score=0.1)
    base.update(kwargs)
    return DerivedMetrics(**base)

# ── Test 1: PUMP-001 vibration breach ────────────────────────────────────────
print("Test 1: Vibration Warning breach")
am = AlarmManager()
m = make_metrics("PUMP-001", vibration_rms_mms=5.2, bearing_temp_c=55.0,
                 pump_efficiency_pct=85.0)
am.evaluate(m)
alarms = am.get_active_alarms()
assert len(alarms) == 1, f"Expected 1 alarm, got {len(alarms)}"
assert alarms[0].level == "Warning"
assert alarms[0].metric == "vibration_rms_mms"
print(f"  ✓ Warning raised: {alarms[0].metric} = {alarms[0].last_value}")

# ── Test 2: Escalate to Alarm ─────────────────────────────────────────────────
print("Test 2: Escalate to Alarm")
m2 = make_metrics("PUMP-001", vibration_rms_mms=7.8, bearing_temp_c=55.0,
                  pump_efficiency_pct=85.0)
am.evaluate(m2)
alarms = am.get_active_alarms()
breach = next(a for a in alarms if a.metric == "vibration_rms_mms")
assert breach.level == "Alarm"
print(f"  ✓ Escalated to Alarm: {breach.metric} = {breach.last_value}")

# ── Test 3: Auto-resolve ──────────────────────────────────────────────────────
print("Test 3: Auto-resolve when back in limits")
m3 = make_metrics("PUMP-001", vibration_rms_mms=2.1, bearing_temp_c=55.0,
                  pump_efficiency_pct=85.0)
am.evaluate(m3)
alarms = am.get_active_alarms()
vib_alarms = [a for a in alarms if a.metric == "vibration_rms_mms"]
assert len(vib_alarms) == 0
print(f"  ✓ Resolved — {len(alarms)} other alarms remain")

# ── Test 4: Watchkeeper trigger queue ────────────────────────────────────────
print("Test 4: Watchkeeper trigger queued on new breach")
am2 = AlarmManager()
m4 = make_metrics("COMP-001", vibration_rms_mms=2.0,
                  volumetric_efficiency_pct=54.0)  # below alarm=55
am2.evaluate(m4)
assert not am2.trigger_queue.empty(), "Expected trigger in queue"
trigger = am2.trigger_queue.get_nowait()
assert trigger["asset_id"] == "COMP-001"
assert trigger["level"] == "Alarm"
print(f"  ✓ Trigger queued: {trigger['asset_id']} {trigger['level']} — {trigger['reason'][:60]}")

# ── Test 5: Debounce ──────────────────────────────────────────────────────────
print("Test 5: Debounce — second breach within window doesn't re-trigger")
am2.evaluate(m4)   # same breach again
assert am2.trigger_queue.empty(), "Should be debounced"
print(f"  ✓ Debounced correctly")

# ── Test 6: CEP integration ───────────────────────────────────────────────────
print("\nTest 6: Full stack — CEP → AlarmManager")
from simulator import create_fleet
from pipeline import broker, DataHarmonizer, CEPEngine
from storage.database import initialise_schema

initialise_schema()
harmonizer = DataHarmonizer()
cep = CEPEngine()
harmonizer.start()
cep.start()

fleet = create_fleet()
fleet["COMP-001"].inject_fault(0.5)   # heavy fault → should breach thresholds

for _ in range(30):
    for asset_id, sim in fleet.items():
        _, msgs = sim.tick()
        broker.publish_many(msgs)
    time.sleep(0.05)
time.sleep(1.5)

active = alarm_manager.get_active_alarms()
print(f"  Active alarms after 30 ticks with COMP-001 faulted: {len(active)}")
for a in active:
    print(f"    [{a.level}] {a.asset_id}.{a.metric} = {a.last_value:.2f} {a.unit}")

print("\nAll alarm tests PASSED.")
