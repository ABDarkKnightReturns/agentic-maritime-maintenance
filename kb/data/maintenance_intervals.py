"""
Standard maintenance intervals for marine machinery.
Sources: Class society rules (DNV, Lloyd's), IACS recommendations, OEM manuals.
"""

MAINTENANCE_INTERVALS = [

    {
        "id": "INT-PUMP-001",
        "text": (
            "Lube oil pump — standard maintenance intervals. "
            "Daily: check bearing temperature (max operating temp typically 70–80 °C), "
            "check for seal leakage, verify flow and pressure against rated values. "
            "Weekly: grease bearings if grease-lubricated type (typically 40–80 g per bearing per week at rated load). "
            "Monthly: check shaft alignment using dial indicator (acceptable misalignment < 0.05 mm parallel, "
            "< 0.02 mm/100 mm angular). Verify coupling condition. "
            "3-Monthly: inspect mechanical seal faces for wear — replace if face run-out > 0.015 mm or "
            "visible grooves. Clean strainer/filter. "
            "Annual (PMS): full overhaul — disassemble, inspect impeller for erosion, measure bearing clearances, "
            "replace wear ring if clearance > 2× original. "
            "6,000–8,000 hours: bearing replacement (rolling element bearings). "
            "ISM Code 10.3 requires all maintenance to be recorded in PMS with date, work done, parts used."
        ),
        "metadata": {
            "category": "maintenance_intervals", "asset_type": "pump",
            "source": "ISM Code 10.3; OEM pump manual; DNV class requirements",
            "topic": "pm_schedule",
        },
    },
    {
        "id": "INT-COMP-001",
        "text": (
            "Starting air compressor — standard maintenance intervals. "
            "Daily: check oil level and quality, verify air receiver pressure (operating pressure 25–30 bar), "
            "drain condensate from receivers and intercoolers, check for abnormal noise/vibration. "
            "Weekly: test safety valves by lifting manually, check all pressure gauges against calibrated reference, "
            "inspect auto-drain function. "
            "250 hours: change crankcase oil, clean oil filter, inspect and clean suction strainer. "
            "1,000 hours: inspect inlet and discharge valves — replace valve plates and springs if worn. "
            "Check piston rings (replace if gap > 1.5× original). "
            "2,000 hours: inspect pistons, connecting rods, and crankshaft bearings. "
            "Measure cylinder liner wear (replace if wear > 0.3 mm or ovality > 0.1 mm). "
            "3,000 hours or annually: full overhaul per OEM schedule. Clean intercooler tubes. "
            "Inspect and test safety valves by pressure testing. "
            "SOLAS II-1/28 compliance check: verify compressor charges receivers to operating pressure within "
            "30 minutes. Document test results."
        ),
        "metadata": {
            "category": "maintenance_intervals", "asset_type": "compressor",
            "source": "SOLAS II-1/28; ISM Code 10.1; Hamworthy OEM manual",
            "topic": "pm_schedule",
        },
    },
    {
        "id": "INT-TURBO-001",
        "text": (
            "Turbocharger — standard maintenance intervals. "
            "Daily: check lube oil level and pressure (minimum supply pressure per OEM spec, "
            "typically 1.5–3.0 bar), check for oil leaks, monitor boost pressure vs. engine load curve. "
            "Weekly: inspect air filter — clean if pressure drop > 25 mbar. "
            "50–100 hours: water-wash compressor side (online washing with engine running at 75–85% MCR "
            "using fresh water; amount per OEM procedure). "
            "500–1,000 hours: dry grit blasting of turbine side (port operation, engine stopped). "
            "Inspect for carbon/ash deposits. "
            "4,000–6,000 hours: inspect nozzle ring and diffuser — check for erosion, verify flow area "
            "(should be within 5% of original). "
            "12,000–16,000 hours: mid-life inspection — remove rotor, check blade condition, measure "
            "bearing clearances, check labyrinth seal clearances. "
            "24,000 hours or per class survey requirement: full overhaul, replace bearings, "
            "balance rotor, replace worn seals. Report to DNV class surveyor."
        ),
        "metadata": {
            "category": "maintenance_intervals", "asset_type": "turbocharger",
            "source": "MAN B&W turbocharger manual; ABB TPL series; DNV class survey requirements",
            "topic": "pm_schedule",
        },
    },
    {
        "id": "INT-PURIF-001",
        "text": (
            "Fuel oil purifier — standard maintenance intervals. "
            "Daily: check bowl speed and compare with rated RPM (deviation < 3%), "
            "check motor current (rising current indicates increased resistance = fouling), "
            "verify sludge discharge cycle timing, check operating water pressure. "
            "Weekly: verify gravity disc is correct for current fuel oil density (measure fuel density "
            "from bunker sample; select disc within ±5 kg/m³ of density per Alfa Laval selection chart). "
            "500 hours: clean disc stack using approved Alfa Laval cleaning agent. "
            "Inspect bowl hood and sliding bowl bottom O-rings — replace if hardened or cracked. "
            "2,000 hours: replace all bowl seals, O-rings, and gaskets. "
            "Inspect disc stack for cracked or deformed discs (replace entire stack if any cracked disc found). "
            "Check spindle bearings and replace if play evident. "
            "Annual: full bowl overhaul. Inspect bowl body for cracks or erosion. "
            "Balance check if bowl vibration increased. "
            "ISM Code 10.1 requirement: OEM engineer or certified technician for bowl bearing replacement."
        ),
        "metadata": {
            "category": "maintenance_intervals", "asset_type": "purifier",
            "source": "Alfa Laval service manual; ISM Code 10.1",
            "topic": "pm_schedule",
        },
    },
    {
        "id": "INT-GEN-001",
        "text": (
            "Auxiliary generator — standard maintenance intervals. "
            "Daily: log load (kW), frequency (Hz), voltage (V), power factor, exhaust temperature per cylinder, "
            "lube oil pressure, coolant temperature, fuel consumption rate. "
            "Weekly: check coolant level and freeze protection, check lube oil level and condition "
            "(take sample if > 250 hours since last change), test automatic start from dead-ship condition, "
            "test alarm and shutdown functions. "
            "250 hours: change engine lube oil and filter, clean air filter, inspect fuel filter. "
            "500 hours: inspect and clean injectors, check injection timing. "
            "Valve clearance check (intake typically 0.3–0.5 mm, exhaust 0.4–0.6 mm cold). "
            "1,000 hours: cylinder head overhaul — remove and inspect valves, seats, and guides. "
            "Measure compression pressure (minimum 70% of rated). "
            "4,000 hours: major overhaul — pistons, rings, liners. "
            "Annual: DNV class survey — insulation resistance test (min 1 MΩ per kV rated voltage), "
            "visual inspection of alternator windings, test of overspeed trip, safety valve test."
        ),
        "metadata": {
            "category": "maintenance_intervals", "asset_type": "generator",
            "source": "Wärtsilä W20 service manual; DNV Rules Pt.4 Ch.8; ISM Code 10.3",
            "topic": "pm_schedule",
        },
    },
    {
        "id": "INT-CLASS-001",
        "text": (
            "Class society survey requirements — DNV continuous survey machinery (CSM). "
            "Under DNV continuous survey machinery (CSM) notation, each machinery item is placed on a "
            "5-year survey cycle with approximately 20% of items inspected annually. "
            "Annual surveys: Safety equipment test, auto/remote control systems, pressure vessels (visual), "
            "generators and electric motors (insulation resistance, protection settings). "
            "Special survey (every 5 years): full inspection of main and auxiliary machinery, "
            "opening and inspection of all pressure vessels, non-destructive testing of crankshafts and "
            "connecting rods, full survey of electrical systems. "
            "Continuous survey items: each item has individual due dates — items must be opened and "
            "presented to surveyor at specified intervals. Missing a survey item due date results in "
            "class being withdrawn or condition of class notation. "
            "Condition monitoring (CM) notation: may allow extended intervals for items with "
            "demonstrated condition monitoring programs. CM program must be approved by DNV. "
            "Relevant DNV rules: Rules for Classification — Ships, Pt.3 Ch.3 (survey arrangements), "
            "Pt.4 Ch.2 (machinery), Pt.4 Ch.8 (electrical installations)."
        ),
        "metadata": {
            "category": "maintenance_intervals", "asset_type": "all",
            "source": "DNV Rules for Classification Ships Pt.3 Ch.3; Pt.4 Ch.2",
            "topic": "class_survey",
        },
    },
]
