import sys, time, uuid
sys.path.insert(0, r'C:\Users\abhis\maritime-maintenance-demo')

from datetime import datetime, timezone
from simulator import create_fleet
from pipeline import broker, DataHarmonizer, CEPEngine
from storage import TimeseriesStore, EventStore, WorkOrderStore
from storage.database import initialise_schema
from models.events import AlertEvent, AlertSeverity, EventType
from models.maintenance import WorkOrder, WorkOrderStatus, MaintenanceType
from data.maintenance_history import MAINTENANCE_HISTORY

# ── Init schema & seed historical work orders ────────────────────────
initialise_schema()
wo_store = WorkOrderStore()
for wo in MAINTENANCE_HISTORY:
    wo_store.save_work_order(wo)
print(f"Seeded {len(MAINTENANCE_HISTORY)} historical work orders")
print("WO summary:", wo_store.get_summary())

# ── Start pipeline + storage ─────────────────────────────────────────
harmonizer = DataHarmonizer()
cep        = CEPEngine()
ts_store   = TimeseriesStore()
ev_store   = EventStore()

harmonizer.start()
cep.start()
ts_store.start()

# ── Run 10 ticks through the full stack ──────────────────────────────
fleet = create_fleet()
for tick in range(10):
    for asset_id, sim in fleet.items():
        _, messages = sim.tick()
        broker.publish_many(messages)
    time.sleep(0.15)

time.sleep(2.0)   # let storage flush

# ── Test: timeseries reads ───────────────────────────────────────────
print("\nTimeseries — PUMP-001 bearing_temp_c (last 5 readings):")
history = ts_store.get_tag_history("PUMP-001", "bearing_temp_c", limit=5)
for row in history:
    print(f"  {row['ts'][-12:]}  {row['value']:.1f} degC")

print("\nDerived history — TURBO-001 (last 3):")
dh = ts_store.get_derived_history("TURBO-001", limit=3)
for row in dh:
    print(f"  {row['ts'][-12:]}  health={row['health_score']}  RUL={row['rul_days']}d")

# ── Test: event store ────────────────────────────────────────────────
ev = AlertEvent(
    event_id=str(uuid.uuid4()),
    asset_id="PUMP-001",
    timestamp=datetime.now(timezone.utc),
    event_type=EventType.THRESHOLD_BREACH,
    severity=AlertSeverity.WARNING,
    title="Bearing temp elevated — 74.2 degC",
    description="Bearing temperature has risen 18°C above baseline over 4 hours.",
    tag="bearing_temp_c",
    observed_value=74.2,
    threshold_value=70.0,
    unit="degC",
    agent_name="realtime_watchkeeper",
    agent_reasoning="Bearing temp trend +0.07 degC/min sustained for 4h. "
                    "Bearing wear index 0.34. Recommend inspection within 48h.",
    recommended_action="Schedule bearing inspection at next port call.",
)
ev_store.save_event(ev)
print("\nActive events:", len(ev_store.get_active_events()))
print("Event saved:", ev_store.get_active_events()[0]["title"])

ev_store.acknowledge_event(ev.event_id, "Chief Engineer")
print("Acknowledged by:", ev_store.get_active_events()[0]["acknowledged_by"])

# ── Test: work order round-trip ──────────────────────────────────────
draft_wo = WorkOrder(
    work_order_id="WO-2026-0001",
    asset_id="PUMP-001",
    maintenance_type=MaintenanceType.CONDITION_BASED,
    status=WorkOrderStatus.DRAFT,
    priority=2,
    title="Lube Oil Pump — Bearing Inspection",
    description="Elevated bearing temp and rising wear index require physical inspection.",
    ai_rationale="Bearing wear index 0.34, temp trend +0.07 degC/min over 4h.",
    created_at=datetime.now(timezone.utc),
    recommended_window="Next port call — Rotterdam 2026-05-22",
    estimated_duration_hours=3.0,
    requires_port=True,
    estimated_cost_usd=800.0,
)
wo_store.save_work_order(draft_wo)
print("\nPending approval:", len(wo_store.get_pending_approval()), "WO(s)")

wo_store.approve_work_order("WO-2026-0001", "Chief Engineer", "Approved — schedule Rotterdam")
approved = wo_store.get_work_order("WO-2026-0001")
print("WO status after approval:", approved.status.value)
print("Approved by:", approved.approved_by)

print("\nAll tests passed.")
