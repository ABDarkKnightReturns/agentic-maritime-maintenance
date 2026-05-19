from datetime import datetime
from models.maintenance import WorkOrder, WorkOrderStatus, MaintenanceType, SparePart

# ---------------------------------------------------------------------------
# Historical completed work orders — used by Agent 2 (Deep Diagnostics)
# to establish baseline degradation rates and by Agent 5 (Fleet Intelligence)
# for fleet-level MTBF calculations
# ---------------------------------------------------------------------------

MAINTENANCE_HISTORY: list[WorkOrder] = [

    WorkOrder(
        work_order_id="WO-2025-0031",
        asset_id="PUMP-001",
        maintenance_type=MaintenanceType.CONDITION_BASED,
        status=WorkOrderStatus.COMPLETED,
        priority=2,
        title="Lube Oil Pump — Mechanical Seal Replacement",
        description="Vibration trend exceeded 4.5 mm/s RMS over 72-hour window. "
                    "Inspection confirmed worn mechanical seal causing minor leakage.",
        ai_rationale="Bearing wear index crossed 0.72 threshold; vibration slope "
                     "+0.08 mm/s per hour sustained for 3 days.",
        created_at=datetime(2025, 11, 18),
        recommended_window="Port call — Rotterdam 2025-11-20",
        estimated_duration_hours=6.0,
        requires_port=True,
        requires_class_surveyor=False,
        approved_by="Chief Engineer",
        approved_at=datetime(2025, 11, 18, 14, 30),
        assigned_to="2nd Engineer",
        started_at=datetime(2025, 11, 20, 9, 0),
        completed_at=datetime(2025, 11, 20, 15, 30),
        completion_notes="Seal replaced, realigned. Vibration returned to 1.8 mm/s post-restart.",
        spare_parts=[
            SparePart(
                part_number="AL-LKH-SEAL-25",
                description="Mechanical seal kit for LKH-25",
                quantity=1,
                lead_time_days=3,
                onboard_stock=2,
            )
        ],
        estimated_cost_usd=1_800.0,
        actual_cost_usd=1_650.0,
        pms_job_code="ME-LOP-001",
        ism_reference="ISM Code 10.1",
    ),

    WorkOrder(
        work_order_id="WO-2025-0019",
        asset_id="COMP-001",
        maintenance_type=MaintenanceType.PLANNED,
        status=WorkOrderStatus.COMPLETED,
        priority=3,
        title="Starting Air Compressor — 4000-Hour Valve Overhaul",
        description="Scheduled PMS overhaul at 20,000 running hours. "
                    "Inlet/outlet valves inspected and replaced. Piston rings checked.",
        ai_rationale="PMS schedule trigger. Compression ratio had also declined from 7.8 to 7.1 "
                     "over 3 months, consistent with valve wear.",
        created_at=datetime(2025, 9, 1),
        recommended_window="Port call — Hamburg 2025-09-05",
        estimated_duration_hours=8.0,
        requires_port=True,
        requires_class_surveyor=False,
        approved_by="Chief Engineer",
        approved_at=datetime(2025, 9, 2, 10, 0),
        assigned_to="2nd Engineer",
        started_at=datetime(2025, 9, 5, 8, 0),
        completed_at=datetime(2025, 9, 5, 17, 0),
        completion_notes="All valves replaced. Compression ratio restored to 7.9 post-overhaul.",
        spare_parts=[
            SparePart(
                part_number="HW-PURUS-VLV-KIT",
                description="Valve overhaul kit — Purus 2-150",
                quantity=1,
                lead_time_days=7,
                onboard_stock=1,
            ),
            SparePart(
                part_number="HW-PURUS-RING-SET",
                description="Piston ring set",
                quantity=1,
                lead_time_days=5,
                onboard_stock=1,
            ),
        ],
        estimated_cost_usd=3_200.0,
        actual_cost_usd=3_100.0,
        pms_job_code="ME-SAC-001",
        ism_reference="ISM Code 10.3",
    ),

    WorkOrder(
        work_order_id="WO-2024-0058",
        asset_id="TURBO-001",
        maintenance_type=MaintenanceType.PLANNED,
        status=WorkOrderStatus.COMPLETED,
        priority=2,
        title="Turbocharger — Nozzle Ring & Blades Inspection",
        description="24,000-hour class-required inspection. Nozzle ring showed "
                    "15% erosion on leading edges. Blades cleaned; no cracks found.",
        ai_rationale="Running hours milestone. Exhaust delta temp had widened by 18°C "
                     "over 6 months — consistent with nozzle ring fouling.",
        created_at=datetime(2024, 12, 5),
        recommended_window="Dry dock — Bremerhaven 2024-12-10",
        estimated_duration_hours=24.0,
        requires_port=True,
        requires_class_surveyor=True,
        approved_by="Superintendent",
        approved_at=datetime(2024, 12, 6, 9, 0),
        assigned_to="Chief Engineer",
        started_at=datetime(2024, 12, 10, 7, 0),
        completed_at=datetime(2024, 12, 11, 10, 0),
        completion_notes="Nozzle ring replaced. Blades cleaned. Class certificate issued. "
                         "Boost pressure restored to 2.8 bar.",
        spare_parts=[
            SparePart(
                part_number="MAN-TCA88-NZ-RING",
                description="Nozzle ring assembly — TCA88-21",
                quantity=1,
                lead_time_days=14,
                onboard_stock=0,
                reorder_required=True,
            )
        ],
        estimated_cost_usd=28_000.0,
        actual_cost_usd=31_500.0,
        pms_job_code="ME-TC-001",
        ism_reference="ISM Code 10.3 / SOLAS II-1",
    ),

    WorkOrder(
        work_order_id="WO-2025-0044",
        asset_id="PURIF-001",
        maintenance_type=MaintenanceType.CONDITION_BASED,
        status=WorkOrderStatus.COMPLETED,
        priority=2,
        title="Fuel Oil Purifier — Bowl & Disc Stack Service",
        description="Bowl speed deviation exceeded 3% and motor current spiked. "
                    "Disc stack partially blocked with sludge; gaskets worn.",
        ai_rationale="Bowl speed deviation 3.4%, motor current +12% above baseline, "
                     "sludge discharge frequency doubled. Multi-sensor anomaly pattern confirmed.",
        created_at=datetime(2025, 10, 15),
        recommended_window="At sea — low sea state window 2025-10-18",
        estimated_duration_hours=10.0,
        requires_port=False,
        requires_class_surveyor=False,
        approved_by="Chief Engineer",
        approved_at=datetime(2025, 10, 16, 8, 0),
        assigned_to="2nd Engineer",
        started_at=datetime(2025, 10, 18, 10, 0),
        completed_at=datetime(2025, 10, 18, 20, 0),
        completion_notes="Disc stack cleaned. Gaskets and O-rings replaced. "
                         "Bowl speed stable at rated RPM post-restart.",
        spare_parts=[
            SparePart(
                part_number="AL-S875-GASKET-KIT",
                description="Bowl gasket and O-ring service kit",
                quantity=1,
                lead_time_days=2,
                onboard_stock=3,
            )
        ],
        estimated_cost_usd=2_100.0,
        actual_cost_usd=1_900.0,
        pms_job_code="ME-FOP-001",
        ism_reference="ISM Code 10.1",
    ),

    WorkOrder(
        work_order_id="WO-2025-0027",
        asset_id="AUXGEN-001",
        maintenance_type=MaintenanceType.PLANNED,
        status=WorkOrderStatus.COMPLETED,
        priority=3,
        title="Auxiliary Generator #2 — 8000-Hour Cylinder Head Overhaul",
        description="Scheduled PMS overhaul. Cylinder head removed, valves reground, "
                    "injectors calibrated. Coolant hoses inspected.",
        ai_rationale="Running hours milestone. Exhaust temp cylinder 3 was 22°C above "
                     "mean — injector calibration drift confirmed.",
        created_at=datetime(2025, 8, 10),
        recommended_window="Port call — Felixstowe 2025-08-14",
        estimated_duration_hours=16.0,
        requires_port=True,
        requires_class_surveyor=False,
        approved_by="Chief Engineer",
        approved_at=datetime(2025, 8, 11, 11, 0),
        assigned_to="Chief Engineer",
        started_at=datetime(2025, 8, 14, 7, 0),
        completed_at=datetime(2025, 8, 15, 2, 0),
        completion_notes="All 6 cylinders serviced. Load test at 110% rated load — passed. "
                         "Fuel consumption reduced by 4%.",
        spare_parts=[
            SparePart(
                part_number="WAR-6L20-INJ-SET",
                description="Injector calibration set — Wärtsilä 6L20",
                quantity=6,
                lead_time_days=5,
                onboard_stock=6,
            ),
            SparePart(
                part_number="WAR-6L20-VALVE-KIT",
                description="Inlet/exhaust valve grinding kit",
                quantity=1,
                lead_time_days=3,
                onboard_stock=2,
            ),
        ],
        estimated_cost_usd=9_500.0,
        actual_cost_usd=9_200.0,
        pms_job_code="EL-AG-002",
        ism_reference="ISM Code 10.3",
    ),
]


def get_history(asset_id: str) -> list[WorkOrder]:
    return [wo for wo in MAINTENANCE_HISTORY if wo.asset_id == asset_id]


def get_all_history() -> list[WorkOrder]:
    return MAINTENANCE_HISTORY
