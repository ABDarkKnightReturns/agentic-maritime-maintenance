"""
IACS Unified Requirements (UR) relevant to engine room machinery.
Sources: IACS UR series — publicly available technical requirements.
"""

IACS_STANDARDS = [

    {
        "id": "IACS-M28",
        "text": (
            "IACS UR M28 — Crankcase explosion relief valves for diesel engines and reciprocating compressors. "
            "Scope: Applies to diesel engines with cylinder bore > 200 mm, power > 220 kW, and reciprocating "
            "air compressors with cylinder bore > 200 mm or total output > 300 kW. "
            "Requirement: Each crankcase must be fitted with relief valves of approved type, sized to provide "
            "adequate relief area (minimum 45 cm² per m³ of crankcase volume). "
            "Self-closing type: valve must re-close automatically after pressure equalisation to prevent air "
            "in-rush (air in-rush after initial pressure wave causes secondary explosion — far more destructive). "
            "For starting air compressors: crankcase must be protected against explosion from oil mist ignition. "
            "Inspection interval: every 2.5 years maximum (or as required by class continuous survey schedule). "
            "Inspection: valve disc and seat condition, spring tension, self-closing function test. "
            "UR M28 applies to COMP-001 if it meets the bore/power threshold. "
            "Typical starting air compressors on merchant vessels: 2-stage, 250–450 kW, bore typically "
            "150–250 mm — check OEM spec for applicability. "
            "Non-compliance with UR M28 is a major ISM non-conformity with class implications."
        ),
        "metadata": {
            "category": "iacs_standards", "asset_type": "compressor",
            "source": "IACS UR M28 (Rev.7 2023)",
            "topic": "crankcase_explosion",
        },
    },
    {
        "id": "IACS-M47",
        "text": (
            "IACS UR M47 — Thermal oil systems (hot oil heaters and heat transfer systems). "
            "Scope: Thermal oil systems used for fuel oil heating — typically applied to fuel oil heaters "
            "and purifier heating circuits on merchant vessels using HFO. "
            "Key requirements: "
            "1. Expansion tank to be fitted with high-level alarm and overflow pipe to settling tank. "
            "2. Thermal oil temperature monitoring — continuous, with alarm at > 20 °C above operating temperature. "
            "3. Vapour detection in thermal oil — expansion tank atmosphere must be monitored for hydrocarbon vapour. "
            "4. No open flame permitted near thermal oil expansion tank. "
            "5. Automatic fire detection in thermal oil heater space. "
            "Relevance to PURIF-001: fuel oil purifier heating circuit uses thermal oil or steam — "
            "overheating of HFO above flash point (typically 60–65 °C for HFO per ISO 8217) is a fire risk. "
            "Fuel oil temperature to purifier: typically 98–102 °C for HFO (viscosity target 15–20 cSt at purifier). "
            "Temperature > 105 °C → risk of flash point exceedance for some blended fuels. "
            "Monitor heating temperature continuously and maintain records per UR M47."
        ),
        "metadata": {
            "category": "iacs_standards", "asset_type": "purifier",
            "source": "IACS UR M47 (Rev.3 2022)",
            "topic": "thermal_oil_heater",
        },
    },
    {
        "id": "IACS-M55",
        "text": (
            "IACS UR M55 — Inspection of exhaust valves and pistons for slow-speed diesel engines. "
            "Scope: Two-stroke crosshead marine diesel engines — relevant to main engine exhaust valves "
            "and the turbocharger condition assessment (exhaust condition directly impacts turbocharger). "
            "Inspection requirements for exhaust valves: "
            "Opening interval: every 8,000–16,000 hours depending on engine type and fuel quality. "
            "With condition monitoring approval: interval may be extended to 24,000 hours per individual assessment. "
            "Inspection criteria: valve seat contact width (should be 4–8 mm, uniform); "
            "spindle straightness (< 0.3 mm per metre); "
            "seat facing hardness (Stellite or equivalent, minimum HRC 35); "
            "valve cage bore wear (max 0.1% of nominal diameter). "
            "Connection to TURBO-001: exhaust valve blow-by causes hot gas ingress to exhaust manifold, "
            "elevating turbine inlet temperature and causing non-uniform temperature distribution across nozzle ring. "
            "Differential exhaust temperature between cylinders > 50 °C indicates valve blow-by — "
            "this will eventually cause turbine nozzle ring erosion if not corrected. "
            "UR M55 requires inspection report to be filed with class surveyor."
        ),
        "metadata": {
            "category": "iacs_standards", "asset_type": "turbocharger",
            "source": "IACS UR M55 (Rev.2 2021)",
            "topic": "exhaust_valve_inspection",
        },
    },
    {
        "id": "IACS-E10",
        "text": (
            "IACS UR E10 — Tests and surveys of electrical machinery. "
            "Scope: Electrical tests required for generators, motors, and switchboards during construction "
            "and periodical surveys. "
            "Periodical survey tests for generators (relevant to AUXGEN-001): "
            "1. Insulation resistance (IR) test — 500V DC megohmmeter for < 1 kV machines, "
            "1000V DC for > 1 kV machines. Minimum acceptable: 1 MΩ per kV of rated voltage, "
            "but not less than 1 MΩ. "
            "2. Winding resistance check — all three phases must be balanced within ±5%. "
            "Imbalance > 5% indicates partial winding fault. "
            "3. Dielectric absorption ratio (DAR): IR at 60 seconds / IR at 30 seconds > 1.4 acceptable. "
            "4. Polarisation index (PI): IR at 10 min / IR at 1 min. "
            "PI > 4.0 = excellent; PI 2.0–4.0 = good; PI 1.0–2.0 = marginal; PI < 1.0 = dangerous. "
            "5. Overspeed test: 20% overspeed for 3 minutes without mechanical damage. "
            "Class requires these tests at every periodical survey (typically every 2.5 years). "
            "Failed IR test prevents return to service — generator must not operate with IR < acceptable level."
        ),
        "metadata": {
            "category": "iacs_standards", "asset_type": "generator",
            "source": "IACS UR E10 (Rev.4 2023)",
            "topic": "electrical_test_requirements",
        },
    },
    {
        "id": "IACS-M67",
        "text": (
            "IACS UR M67 — Centrifugal pumps for essential services. "
            "Scope: Centrifugal pumps used for essential services including lube oil service, fuel oil service, "
            "cooling water, and bilge pumping. Applies to pumps rated above 5 kW on vessels over 500 GT. "
            "Design requirements: "
            "1. Pumps for essential services must have at least one standby pump of equivalent capacity "
            "or another approved means of achieving the same function. "
            "2. Mechanical seals must be of a type that maintains effective sealing up to maximum working "
            "pressure with positive shut-off. "
            "3. Relief valves required on discharge side of positive displacement pumps (not centrifugal). "
            "Survey requirements: "
            "Lube oil pumps: inspect at every class survey (every 2.5 years minimum). "
            "Open and inspect impeller, wear rings, shaft, and mechanical seal at 5-year special survey. "
            "For PUMP-001 (lube oil pump): essential service — standby pump required per UR M67. "
            "Failure of primary lube oil pump without operable standby = major non-conformity. "
            "Redundancy verification required at annual ISM audit. "
            "Record keeping: all pump maintenance must be documented in PMS per ISM Code 10.3."
        ),
        "metadata": {
            "category": "iacs_standards", "asset_type": "pump",
            "source": "IACS UR M67 (Rev.3 2022)",
            "topic": "centrifugal_pump_standards",
        },
    },
]
