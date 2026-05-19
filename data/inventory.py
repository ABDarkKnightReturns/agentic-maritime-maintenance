from datetime import datetime
from models.asset import Asset, AssetType, AssetStatus, HealthTier

# ---------------------------------------------------------------------------
# MV Eindhoven — Engine Room Asset Master Records
# Five monitored assets, each mapped to a real ship equipment category
# ---------------------------------------------------------------------------

ASSETS: dict[str, Asset] = {

    "PUMP-001": Asset(
        asset_id="PUMP-001",
        display_name="Lube Oil Pump #1",
        asset_type=AssetType.PUMP,
        vessel="MV-Eindhoven",
        location="Engine Room — Aft, Frame 42",
        manufacturer="Alfa Laval",
        model_number="LKH-25/155",
        commissioned_date=datetime(2021, 3, 15),
        rated_power_kw=11.0,
        running_hours=18_240.0,          # ~6 years at half load
        class_society="DNV",
        imo_equipment_code="LO-PUMP-01",
        pms_job_code="ME-LOP-001",
        last_maintenance=datetime(2025, 11, 20),
        next_scheduled_maintenance=datetime(2026, 8, 1),
    ),

    "COMP-001": Asset(
        asset_id="COMP-001",
        display_name="Starting Air Compressor #1",
        asset_type=AssetType.COMPRESSOR,
        vessel="MV-Eindhoven",
        location="Engine Room — Port Side, Frame 38",
        manufacturer="Hamworthy",
        model_number="Purus 2-150",
        commissioned_date=datetime(2020, 7, 10),
        rated_power_kw=22.0,
        running_hours=21_500.0,
        class_society="DNV",
        imo_equipment_code="SA-COMP-01",
        pms_job_code="ME-SAC-001",
        last_maintenance=datetime(2025, 9, 5),
        next_scheduled_maintenance=datetime(2026, 6, 15),
    ),

    "TURBO-001": Asset(
        asset_id="TURBO-001",
        display_name="Main Engine Turbocharger",
        asset_type=AssetType.TURBOCHARGER,
        vessel="MV-Eindhoven",
        location="Engine Room — Centre, Main Engine",
        manufacturer="MAN Energy Solutions",
        model_number="TCA88-21",
        commissioned_date=datetime(2019, 5, 22),
        rated_power_kw=850.0,           # Turbocharger work equivalent
        running_hours=34_800.0,         # High hours — approaching overhaul
        class_society="DNV",
        imo_equipment_code="ME-TC-01",
        pms_job_code="ME-TC-001",
        last_maintenance=datetime(2024, 12, 10),
        next_scheduled_maintenance=datetime(2026, 7, 1),
    ),

    "PURIF-001": Asset(
        asset_id="PURIF-001",
        display_name="Fuel Oil Purifier",
        asset_type=AssetType.PURIFIER,
        vessel="MV-Eindhoven",
        location="Engine Room — Purifier Room, Frame 35",
        manufacturer="Alfa Laval",
        model_number="S-875",
        commissioned_date=datetime(2021, 3, 15),
        rated_power_kw=7.5,
        running_hours=17_600.0,
        class_society="DNV",
        imo_equipment_code="FO-PURIF-01",
        pms_job_code="ME-FOP-001",
        last_maintenance=datetime(2025, 10, 18),
        next_scheduled_maintenance=datetime(2026, 5, 30),
    ),

    "AUXGEN-001": Asset(
        asset_id="AUXGEN-001",
        display_name="Auxiliary Generator #2",
        asset_type=AssetType.GENERATOR,
        vessel="MV-Eindhoven",
        location="Engine Room — Starboard, Frame 40",
        manufacturer="Wärtsilä",
        model_number="6L20 / Stamford HC6",
        commissioned_date=datetime(2019, 5, 22),
        rated_power_kw=910.0,
        running_hours=29_100.0,
        class_society="DNV",
        imo_equipment_code="ELEC-GEN-02",
        pms_job_code="EL-AG-002",
        last_maintenance=datetime(2025, 8, 14),
        next_scheduled_maintenance=datetime(2026, 6, 1),
    ),
}


def get_asset(asset_id: str) -> Asset:
    if asset_id not in ASSETS:
        raise KeyError(f"Unknown asset: {asset_id}. Valid IDs: {list(ASSETS.keys())}")
    return ASSETS[asset_id]


def all_assets() -> list[Asset]:
    return list(ASSETS.values())


def assets_by_type(asset_type: AssetType) -> list[Asset]:
    return [a for a in ASSETS.values() if a.asset_type == asset_type]
