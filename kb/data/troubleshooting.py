"""
Diagnostic and troubleshooting guides for marine machinery.
Covers vibration analysis, efficiency interpretation, temperature deviations,
and condition assessment decision trees.
"""

TROUBLESHOOTING = [

    {
        "id": "TS-VIB-FREQ",
        "text": (
            "Vibration frequency analysis — fault identification from dominant frequency components. "
            "1× running speed (fundamental): shaft unbalance (most common), misalignment (also generates 2×), "
            "bent shaft, eccentric rotor. Characteristic: large 1× amplitude, relatively low harmonics. "
            "2× running speed: angular misalignment, looseness (structural), cracked shaft. "
            "Parallel misalignment generates predominantly 1×; angular misalignment generates 2×. "
            "3× and higher harmonics: mechanical looseness, rub contact, impeller flow turbulence. "
            "Bearing defect frequencies: "
            "BPFO (ball pass frequency outer race) = n/2 × RPM/60 × (1 - Bd/Pd × cos α). "
            "BPFI (ball pass frequency inner race) = n/2 × RPM/60 × (1 + Bd/Pd × cos α). "
            "BSF (ball spin frequency) = Pd/(2×Bd) × RPM/60 × (1 - (Bd/Pd × cos α)²). "
            "Where n = number of rolling elements, Bd = ball diameter, Pd = pitch diameter, α = contact angle. "
            "Sub-synchronous (< 1×): oil whirl (0.43–0.48×), surge instability, oil whip (locked at resonance). "
            "Broadband random vibration: cavitation, flow turbulence, loose components. "
            "Practical rule: if dominant frequency is exactly at a bearing defect frequency AND amplitude "
            "is rising week-over-week, bearing failure is progressing — schedule replacement within 2–4 weeks."
        ),
        "metadata": {
            "category": "troubleshooting", "asset_type": "all",
            "source": "ISO 13373-1; ISO 13373-3; vibration analysis handbook",
            "topic": "vibration_frequency_analysis",
        },
    },
    {
        "id": "TS-VIB-TREND",
        "text": (
            "Vibration trend analysis and alarm level setting for shipboard machinery. "
            "Baseline establishment: record vibration at commissioning or after overhaul at rated load conditions. "
            "Baseline should be the mean of 5 measurements at identical load conditions. "
            "Alert levels (MIMOSA/ISO 13373 recommended practice): "
            "Warning level: baseline + 25% of Zone B limit (ISO 10816-3). For Class III machinery "
            "(> 300 kW rigid foundation), Zone B limit = 4.5 mm/s, so warning = 4.5 + (0.25 × 4.5) = 5.6 mm/s. "
            "Alarm level: Zone B/C boundary = 7.1 mm/s (Class III). "
            "Danger/trip: Zone C/D boundary = 11.2 mm/s (Class III). "
            "Trend rate of change: if vibration increases > 0.5 mm/s per week, investigate immediately "
            "regardless of absolute level (early warning of accelerating degradation). "
            "Step change: if vibration jumps > 1.5 mm/s in a single measurement period, take immediate action "
            "(indicates sudden change — loose component, impact damage, or measurement artefact). "
            "Load normalisation: always compare vibration at same load ±5%. Vibration typically increases "
            "with load; comparing different load points creates false trends. "
            "Seasonal temperature effects: cold oil increases bearing stiffness, can reduce vibration by "
            "10–15% — account for seasonal variation in trend baselines."
        ),
        "metadata": {
            "category": "troubleshooting", "asset_type": "all",
            "source": "ISO 13373-1; ISO 10816-3; MIMOSA OSACBM standard",
            "topic": "vibration_trending",
        },
    },
    {
        "id": "TS-PUMP-DIAG",
        "text": (
            "Centrifugal pump diagnostic decision tree — interpreting combined sensor readings. "
            "Symptom: High vibration + normal differential pressure + normal flow rate → "
            "Likely: bearing problem, misalignment, or imbalance. Not cavitation (dP and Q normal). "
            "Check: bearing temperature, vibration spectrum (look for 1× dominant = imbalance/misalign; "
            "bearing defect frequencies = bearing wear). "
            "Symptom: Normal vibration + low differential pressure + low flow rate → "
            "Likely: impeller wear (wear rings worn — internal recirculation), suction restriction, "
            "or system resistance changed. Pump on wrong point of H-Q curve. "
            "Check: measure suction pressure, inspect suction strainer, compare dP against pump curve at measured flow. "
            "Symptom: High vibration + low dP + unstable flow → "
            "Likely: cavitation. Noise characteristic: crackling/popping from casing. "
            "Check: NPSH available (suction head), oil temperature (viscosity), strainer condition. "
            "Symptom: Rising bearing temperature + normal vibration → "
            "Likely: bearing lubrication failure, or bearing running in (after overhaul, normal for 2–4 hours). "
            "Check: oil/grease level, oil quality (oxidation, water contamination), bearing clearance. "
            "Any single parameter alone is insufficient for diagnosis — always cross-reference at least "
            "2 parameters and maintenance history before concluding root cause."
        ),
        "metadata": {
            "category": "troubleshooting", "asset_type": "pump",
            "source": "Pump engineering handbook; ISO 13373",
            "topic": "pump_diagnosis",
        },
    },
    {
        "id": "TS-TURBO-DIAG",
        "text": (
            "Turbocharger diagnostic decision tree — interpreting combined parameters. "
            "Symptom: Boost pressure dropping + exhaust temperature rising + efficiency dropping → "
            "Likely: compressor blade fouling (most common cause at sea). "
            "Distinguish from blade damage: fouling gives gradual trend; damage gives step change. "
            "Action: online water-wash; if no improvement in 2 hours, port inspection required. "
            "Symptom: Boost pressure oscillating + loud banging noise + high vibration → "
            "Certain: surge event. Load reduction mandatory. Investigate after stabilisation. "
            "Post-surge inspection: check for casing contact marks on compressor wheel. "
            "Symptom: Vibration rising sub-synchronously (< 0.5× speed) + oil outlet temperature high → "
            "Likely: bearing failure in progress (oil whirl). Reduce load. "
            "If sub-synchronous amplitude locked at constant frequency while speed changes = oil whip — "
            "bearing failure imminent, take out of service. "
            "Symptom: Individual cylinder exhaust temperatures widening + turbine inlet temperature uneven → "
            "Likely: fuel injector fault or exhaust valve blow-by causing uneven energy input to turbine. "
            "Investigate cylinder-by-cylinder; turbocharger is secondary effect. "
            "Exhaust temperature spread > 50 °C (cylinder-to-mean): source is engine, not turbocharger."
        ),
        "metadata": {
            "category": "troubleshooting", "asset_type": "turbocharger",
            "source": "MAN B&W turbocharger manual; ABB diagnostic guide",
            "topic": "turbocharger_diagnosis",
        },
    },
    {
        "id": "TS-COMP-DIAG",
        "text": (
            "Starting air compressor diagnostic decision tree. "
            "Symptom: Volumetric efficiency dropping + stage discharge temperature rising → "
            "Likely: valve failure (inlet or discharge valve leaking past seat). "
            "Test: stop compressor, isolate, open valve chest — inspect valve plates for cracks or lifted seats. "
            "Feel each valve immediately after stopping: a warm valve suggests it has been passing gas (leaking). "
            "Symptom: Crankcase pressure positive (> 0 bar gauge) + oil consumption rising → "
            "Likely: piston ring blow-by. "
            "Confirm: crankcase vent discharge has elevated hydrocarbon smell and oiliness. "
            "Risk assessment: IACS UR M28 — elevated crankcase pressure is explosion risk. "
            "Symptom: High stage 1 temperature + normal stage 2 temperature → "
            "Likely: inter-stage cooler fouled or inlet temperature high. "
            "Calculate expected stage outlet temperature: for ideal compression, T2 = T1 × (P2/P1)^((γ-1)/γ) "
            "where γ = 1.4 for air. If measured > theoretical by > 15 °C, cooler efficiency degraded. "
            "Symptom: Compressor running long cycle + receivers charging slowly → "
            "Likely: air leak in system (check receiver drain valves, pipework joints), "
            "or decreased compressor output (efficiency degraded). "
            "Leak test: charge to full pressure, isolate compressor, monitor pressure drop rate. "
            "Acceptable leak rate: < 0.3 bar/hour at 30 bar."
        ),
        "metadata": {
            "category": "troubleshooting", "asset_type": "compressor",
            "source": "Hamworthy compressor manual; practical troubleshooting guide",
            "topic": "compressor_diagnosis",
        },
    },
    {
        "id": "TS-RUL-ESTIMATE",
        "text": (
            "Remaining Useful Life (RUL) estimation methodology for marine rotating machinery. "
            "Linear degradation model (appropriate for wear-dominated failures): "
            "RUL = (Health_threshold - Health_current) / degradation_rate. "
            "Where degradation_rate = (Health_baseline - Health_current) / operating_hours_since_baseline. "
            "Health threshold for intervention: typically 30–40% for critical machinery (below this, "
            "failure probability in next maintenance interval > 50%). "
            "Confidence intervals: widen RUL estimate by ±30% for medium confidence, ±50% for low confidence. "
            "Weibull failure analysis: for components with known failure distributions (from fleet data), "
            "Weibull β < 1.0 = infant mortality (early failures); β ≈ 1.0 = random failures; "
            "β > 1.0 = wear-out failures (most mechanical components β = 1.5–3.5). "
            "For bearings specifically: SKF/ISO 281 L10 life — 90% of bearings survive to calculated hours. "
            "MTBF-based RUL: if historical MTBF is known (e.g., from fleet records), and current health score "
            "is declining at known rate, extrapolate to MTBF as upper bound on RUL. "
            "Communication of RUL to Chief Engineer: always state confidence level and key assumptions. "
            "Example: 'RUL estimated 14–21 days at current degradation rate (medium confidence); "
            "assumes linear continuation of vibration trend observed over past 72 hours.'"
        ),
        "metadata": {
            "category": "troubleshooting", "asset_type": "all",
            "source": "ISO 13381-1 (RUL); Weibull analysis; SKF bearing handbook",
            "topic": "rul_estimation",
        },
    },
    {
        "id": "TS-HEALTH-SCORE",
        "text": (
            "Health score interpretation and intervention thresholds for shipboard machinery. "
            "Health score scale: 0–100, where 100 = new/just overhauled condition. "
            "Score bands and recommended actions: "
            "90–100 (Excellent): Normal operation. Continue scheduled monitoring. "
            "75–89 (Good): Normal operation. Vibration and temperatures within Zone A/B (ISO 10816). "
            "60–74 (Fair — Condition Alert): Increase monitoring frequency. Schedule inspection at next "
            "convenient opportunity (port call or planned maintenance period). Prepare spare parts. "
            "40–59 (Poor — Action Required): Plan maintenance within 14–21 days. "
            "Restrict non-essential load on asset. Chief Engineer to personally verify condition. "
            "Consider running spare/standby continuously. "
            "20–39 (Critical — Urgent): Maintenance within 72 hours. Consider immediate reduction in load. "
            "Verify standby is operational. Flag for port state control awareness. "
            "Notify class surveyor if condition monitoring program is approved. "
            "0–19 (Failure Imminent): Take asset off-load immediately if safe. Emergency work order. "
            "These thresholds align with ISO 10816 vibration zones and are consistent with "
            "industry condition monitoring practices (DNV Veritas Marine Services guidance)."
        ),
        "metadata": {
            "category": "troubleshooting", "asset_type": "all",
            "source": "DNV condition monitoring guidance; ISO 10816-3; industry practice",
            "topic": "health_score_thresholds",
        },
    },
]
