import sys, time
sys.path.insert(0, r'C:\Users\abhis\maritime-maintenance-demo')

from simulator import create_fleet
from pipeline import broker, DataHarmonizer, CEPEngine
from storage import TimeseriesStore, EventStore, WorkOrderStore
from storage.database import initialise_schema
from data.maintenance_history import MAINTENANCE_HISTORY
from agents import create_agents

# ── Boot the stack ────────────────────────────────────────────────────
initialise_schema()
wo_store  = WorkOrderStore()
ev_store  = EventStore()
ts_store  = TimeseriesStore()

for wo in MAINTENANCE_HISTORY:
    wo_store.save_work_order(wo)

harmonizer = DataHarmonizer()
cep        = CEPEngine()
harmonizer.start()
cep.start()
ts_store.start()

# ── Run 30 ticks and inject a fault on PUMP-001 ───────────────────────
fleet = create_fleet()
fleet["PUMP-001"].inject_fault(severity=0.25)   # drop health → make it interesting
fleet["COMP-001"].inject_fault(severity=0.15)

print("Running 30 simulator ticks with faults injected...")
for tick in range(30):
    for asset_id, sim in fleet.items():
        _, messages = sim.tick()
        broker.publish_many(messages)
    time.sleep(0.1)

time.sleep(2.0)  # let CEP compute

# Show CEP state before agent
print("\nPre-agent CEP state:")
for asset_id, m in cep.latest_derived.items():
    print(f"  {asset_id}: health={m.overall_health_score:.1f} RUL={m.rul_days:.1f}d anomaly={m.anomaly_score:.3f}")

# ── Run Agent 1 (Watchkeeper) — cheapest / fastest ────────────────────
ctx = {"ts_store": ts_store, "ev_store": ev_store, "wo_store": wo_store, "cep": cep}
agents = create_agents(ctx)

print("\n" + "="*60)
print("AGENT 1 — Realtime Watchkeeper (claude-haiku-4-5)")
print("="*60)
result = agents["watchkeeper"].run()
print(f"\nDuration: {result.duration_s}s")
print(f"Actions taken: {len(result.actions_taken)}")
for a in result.actions_taken:
    print(f"  Tool: {a['tool']}")
print("\n--- Agent Output ---")
print(result.full_reasoning)

# Show what was saved
active = ev_store.get_active_events()
print(f"\nAlerts in event store: {len(active)}")
for ev in active[:3]:
    print(f"  [{ev['severity']}] {ev['asset_id']}: {ev['title']}")
