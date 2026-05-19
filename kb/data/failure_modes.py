"""
Maritime failure mode knowledge base.
Covers all 5 monitored assets: pump, compressor, turbocharger, purifier, generator.
Sources: MAN B&W, Alfa Laval, Hamworthy, Wärtsilä OEM guidelines; ISO 13373; ISO 10816.
"""

FAILURE_MODES = [

    # ── PUMP-001: Lube Oil Pump (centrifugal) ─────────────────────────────────

    {
        "id": "PUMP-BRG-001",
        "text": (
            "Lube oil pump bearing failure — rolling element bearings. "
            "Symptom pattern: vibration RMS increases progressively, initially dominant at 1× running speed, "
            "then broadband noise floor rises as raceway spalling develops. Bearing temperature rises 10–20 °C "
            "above baseline. Differential pressure and flow rate remain stable until late stage. "
            "Root cause: lubricant contamination (water ingress, particulates), overloading, misalignment, "
            "or extended operation beyond rated hours. "
            "ISO 13373-3 classification: defect frequency harmonics (BPFO, BPFI, BSF) visible in spectrum. "
            "Action: vibration > 4.5 mm/s RMS (ISO 10816-3 Zone B/C boundary) → schedule inspection within 14 days. "
            "Vibration > 7.1 mm/s RMS (Zone C/D boundary) → restrict operation, inspect within 48 hours. "
            "OEM reference: check bearing clearance (radial play < 0.05 mm for most centrifugal pump bearings), "
            "replace bearing if inner race shows blue discolouration or pitting."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "pump",
            "source": "ISO 13373-3; ISO 10816-3; OEM pump manual",
            "topic": "bearing_failure", "severity": "high",
        },
    },
    {
        "id": "PUMP-SEAL-001",
        "text": (
            "Lube oil pump mechanical seal wear and failure. "
            "Symptom pattern: initial leakage at seal face visible as oil weeping or mist around seal housing. "
            "Efficiency drops as seal chamber pressure balance is lost. Bearing temperature may rise slightly "
            "due to contamination of bearing lubricant. "
            "Root cause: abrasive particles in oil, thermal shock from dry-running, axial shaft movement "
            "beyond seal design tolerance (typically ±0.5 mm), chemical incompatibility with oil additives. "
            "Failure progression: face wear → leakage → oil contamination → bearing failure cascade. "
            "Action: any visible shaft seal leakage in lube oil system is a major non-conformity under ISM Code 10.1 "
            "due to fire risk. Seal replacement should be completed at next port; interim measure is to increase "
            "inspection frequency to 4-hourly and monitor bilge levels. "
            "Typical seal life: 8,000–12,000 running hours."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "pump",
            "source": "ISM Code Section 10; OEM pump manual",
            "topic": "seal_failure", "severity": "high",
        },
    },
    {
        "id": "PUMP-CAVI-001",
        "text": (
            "Centrifugal pump cavitation and impeller erosion. "
            "Symptom pattern: irregular crackling noise (like gravel in pump casing), vibration increases "
            "at random frequencies rather than harmonic pattern, differential pressure drops and fluctuates, "
            "flow rate becomes unstable. Pump efficiency drops 10–30% in developed cavitation. "
            "Root cause: suction head insufficient (NPSH available < NPSH required), suction strainer fouled, "
            "oil temperature too high reducing viscosity, excessive running speed. "
            "Damage mechanism: vapour bubble collapse on impeller vanes causes micro-jet impact erosion, "
            "progressive pitting of impeller leading edge. "
            "Action: check suction strainer (clean if pressure drop > 0.3 bar), verify suction head, "
            "reduce pump speed if possible. Impeller inspection required if cavitation noise persists > 4 hours. "
            "Eroded impeller reduces pump head by approximately 5% per 0.5 mm leading-edge material loss."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "pump",
            "source": "OEM pump manual; hydraulic machinery handbook",
            "topic": "cavitation", "severity": "medium",
        },
    },

    # ── COMP-001: Starting Air Compressor (reciprocating) ────────────────────

    {
        "id": "COMP-VALVE-001",
        "text": (
            "Starting air compressor inlet and discharge valve failure. "
            "Symptom pattern: volumetric efficiency drops progressively (normal > 75%, warning < 65%, alarm < 55%). "
            "Intercooler and aftercooler discharge temperature rises as more gas recirculates past damaged valve. "
            "Compressor takes longer to charge air receivers to operating pressure (25–30 bar). "
            "Vibration shows increased 2× running speed component and irregular impact signature. "
            "Root cause: valve plate fatigue cracking (most common — high-cycle fatigue at 400–800 cycles/min), "
            "seat erosion from particulates, valve spring fatigue, carbon deposit build-up restricting travel. "
            "Failure consequence: loss of starting air capability — SOLAS II-1/28 requires minimum 12 starts for "
            "reversible main engines, 6 starts for non-reversible. Below threshold = major non-conformity. "
            "Action: inspect valves every 3,000 hours or annually (whichever sooner). Replace valve plates "
            "at first sign of cracking. Hamworthy OEM specifies valve plate hardness HRC 58–62."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "compressor",
            "source": "SOLAS II-1/28; Hamworthy OEM manual; ISM Code 10.1",
            "topic": "valve_failure", "severity": "critical",
        },
    },
    {
        "id": "COMP-RING-001",
        "text": (
            "Starting air compressor piston ring blow-by. "
            "Symptom pattern: crankcase pressure rises above normal (> 0.05 bar positive pressure). "
            "Lubricating oil consumption increases. Compression ratio drops progressively. "
            "Discharge temperature rises as compression work increases to compensate for blow-by. "
            "High-pressure cylinder blow-by detectable as elevated hydrocarbon content in crankcase vent. "
            "Root cause: ring wear (normal wear rate ~0.01 mm/1000h), groove wear, ring sticking from "
            "carbon deposits (inadequate lubrication or overloading), thermal distortion from overheating. "
            "Risk: elevated crankcase pressure with oil mist creates explosion risk — IACS UR M28 requires "
            "crankcase relief valves for compressors > 200 mm bore or > 300 kW. "
            "Action: check crankcase pressure weekly. Piston ring replacement interval typically 8,000–12,000 hours. "
            "If compression ratio drops below 60% of rated value, compressor must be taken out of service."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "compressor",
            "source": "IACS UR M28; OEM compressor manual",
            "topic": "piston_ring_blowby", "severity": "high",
        },
    },
    {
        "id": "COMP-COOL-001",
        "text": (
            "Starting air compressor intercooler fouling and aftercooler blockage. "
            "Symptom pattern: stage discharge temperatures rise uniformly across compression stages. "
            "Intercooler approach temperature (difference between coolant outlet and air outlet) increases "
            "from normal 3–5 °C to > 10 °C indicating fouling. Compressor trips on high temperature alarm. "
            "Root cause: tube-side fouling from oil carryover (indicates ring blow-by or excessive lubrication), "
            "water-side fouling from scale deposits in freshwater cooling, bio-fouling in seawater cooling. "
            "Consequence: higher air temperature reduces effective starting air capacity (air is less dense). "
            "Air moisture content increases, accelerating corrosion in air receivers and pipework. "
            "Action: clean intercooler tubes chemically if approach temperature > 8 °C. "
            "Check oil carry-over: oil content in compressed air should be < 5 mg/m³ per ISO 8573-1. "
            "Inspect air receiver for corrosion during annual class survey."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "compressor",
            "source": "ISO 8573-1; OEM compressor manual",
            "topic": "intercooler_fouling", "severity": "medium",
        },
    },

    # ── TURBO-001: Turbocharger (axial turbine, centrifugal compressor) ───────

    {
        "id": "TURBO-FOUL-001",
        "text": (
            "Turbocharger compressor wheel and turbine blade fouling. "
            "Symptom pattern: boost pressure drops progressively at constant engine load. "
            "Exhaust gas temperature before turbine rises (engine works harder to maintain power). "
            "Exhaust delta temperature across cylinders remains even (distinguishes from fuel injector issue). "
            "Turbocharger efficiency drops (normal > 70%, warning < 60%). Surge margin reduces. "
            "Root cause: compressor side — oil mist and salt deposits from combustion air build up on "
            "compressor blades, altering aerodynamic profile. Turbine side — carbon and ash deposits from "
            "incomplete combustion, particularly with high-sulphur fuels or at low load operation. "
            "MAN B&W recommendation: water-wash compressor side every 50–100 operating hours at sea; "
            "dry grit cleaning of turbine side during in-port maintenance. "
            "Action: boost pressure drop > 10% from baseline → schedule wash within 48 hours. "
            "Surging incidents → immediate load reduction and wash."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "turbocharger",
            "source": "MAN B&W turbocharger service manual; ABB TPL series bulletin",
            "topic": "blade_fouling", "severity": "medium",
        },
    },
    {
        "id": "TURBO-SURGE-001",
        "text": (
            "Turbocharger surge — compressor instability. "
            "Symptom pattern: loud periodic banging from turbocharger casing (1–5 Hz), boost pressure "
            "oscillates violently, exhaust smoke increases. Vibration spikes dramatically during surge event. "
            "Surge margin < 10% is dangerous operating condition. "
            "Root cause: operating point moves left of compressor surge line on map due to: fouled blades "
            "(reduces surge margin), rapid engine load reduction (air excess collapses), high back-pressure "
            "from fouled exhaust gas boiler, fuel quality change affecting combustion rate. "
            "Damage mechanism: reverse axial thrust during surge can damage rotor bearings and cause "
            "compressor wheel contact with casing. Repeated surging can fatigue-crack compressor wheel. "
            "Surge is most likely cause of turbocharger bearing failure in service. "
            "Action: reduce engine load immediately, investigate root cause. If surging continues at any load, "
            "take engine off-load and inspect before resuming. Notify class surveyor if surge causes bearing damage. "
            "Post-surge inspection mandatory per MAN B&W B&W engine builder requirement."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "turbocharger",
            "source": "MAN B&W turbocharger service manual; ISO 10438",
            "topic": "surge", "severity": "critical",
        },
    },
    {
        "id": "TURBO-BRG-001",
        "text": (
            "Turbocharger bearing failure — floating ring journal bearings. "
            "Symptom pattern: vibration at 1× and sub-synchronous frequencies (typically 0.4–0.48× running speed "
            "from oil whirl in floating ring bearings). Lube oil outlet temperature rises > 15 °C above normal. "
            "Rotor coast-down time decreases (indicates increased bearing friction). "
            "Abnormal noise — metallic whine or grind during acceleration or deceleration. "
            "Root cause: lube oil contamination, inadequate oil supply pressure (minimum 1.5–3.0 bar required "
            "depending on model), oil viscosity mismatch, turbocharger overspeed, shaft imbalance from "
            "blade damage or fouling. "
            "Turbocharger speed range: typically 10,000–30,000 RPM for marine turbos — bearing tolerances are "
            "critical, radial clearance typically 0.08–0.15 mm for floating ring design. "
            "Action: bearing inspection when oil temperature rise > 10 °C baseline. "
            "Sub-synchronous vibration is diagnostic for oil whirl — reduce oil supply temperature and check pressure. "
            "ABB service bulletin SB-TC-2021-04 specifies bearing replacement at 24,000 running hours."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "turbocharger",
            "source": "ABB turbocharger service bulletin; ISO 13373",
            "topic": "bearing_failure", "severity": "high",
        },
    },

    # ── PURIF-001: Fuel Oil Purifier (disc centrifuge, Alfa Laval type) ────────

    {
        "id": "PURIF-DISC-001",
        "text": (
            "Fuel oil purifier disc stack fouling and bowl imbalance. "
            "Symptom pattern: bowl speed drops below rated (normal speed typically 6,000–8,000 RPM). "
            "Motor current increases as viscous resistance increases from fouled disc stack. "
            "Separation efficiency drops — fuel oil density after purifier approaches feed density. "
            "Sludge discharge volume decreases (sludge not reaching periphery). Bowl vibration increases. "
            "Root cause: asphaltene and carbon deposits on disc surfaces narrow the flow channels between discs "
            "(typical disc gap 0.3–0.5 mm). Incomplete cleaning cycles allow build-up. "
            "High-sulphur residual fuel oil accelerates fouling. "
            "Alfa Laval recommendation: disc stack cleaning every 500 operating hours or when bowl speed "
            "drops > 3% from rated speed. Use approved cleaning agent per Alfa Laval procedure. "
            "Action: bowl speed deviation > 5% → clean disc stack within 24 hours. "
            "> 10% deviation or increased vibration → stop and inspect bowl for imbalance/wear. "
            "A cracked disc is a serious safety issue — bowl failure at speed is catastrophic."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "purifier",
            "source": "Alfa Laval FOPX/WHPX service manual; MEPC guidelines",
            "topic": "disc_fouling", "severity": "high",
        },
    },
    {
        "id": "PURIF-SEAL-001",
        "text": (
            "Fuel oil purifier operating water system and seal ring failure. "
            "Symptom pattern: water seal fails → fuel oil discharges with sludge (water/oil carry-over). "
            "Gravity disc wrong size → interface displaced incorrectly → oil carry-over to water phase. "
            "Sludge discharge frequency increases without corresponding sludge volume. "
            "Root cause: O-ring deterioration on bowl hood and sliding bowl bottom (replace every 2,000 hours). "
            "Gravity disc size incorrect for current fuel oil density (disc size must match density ±5 kg/m³). "
            "Operating water pressure < 1.5 bar prevents water seal formation. "
            "Alfa Laval gravity disc selection: for HFO at 991 kg/m³ at 15°C, use appropriate disc per table. "
            "Incorrect gravity disc is the most common cause of purifier oil loss incidents. "
            "Action: verify gravity disc size when switching fuel or receiving new bunkers. "
            "Check O-ring condition at every disc stack cleaning interval. "
            "MARPOL Annex I: any overboard discharge of oily mixture > 15 ppm is a violation."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "purifier",
            "source": "Alfa Laval service manual; MARPOL Annex I; IMO MEPC.1/Circ.642",
            "topic": "seal_operating_water", "severity": "high",
        },
    },

    # ── AUXGEN-001: Auxiliary Generator (diesel genset) ───────────────────────

    {
        "id": "GEN-INJECTOR-001",
        "text": (
            "Auxiliary generator fuel injector wear and blockage. "
            "Symptom pattern: exhaust temperature rises on specific cylinders (cylinder-by-cylinder exhaust "
            "thermocouple deviation > 20 °C from mean is significant). Specific fuel consumption increases "
            "(normal: 185–210 g/kWh; warning: > 220 g/kWh). Governor hunting at steady load. "
            "Exhaust smoke — blue/white smoke indicates late injection or poor atomisation. "
            "Root cause: nozzle tip erosion from abrasive particles, needle seizure from fuel contamination, "
            "carbon deposit on nozzle holes reducing effective orifice area, spring fatigue reducing opening pressure. "
            "Opening pressure typically 250–400 bar (varies by engine); drop > 20 bar indicates spring fatigue. "
            "Action: single cylinder exhaust temp deviation > 30 °C → test injector on pop tester at next opportunity. "
            "Injector overhaul interval: every 4,000 hours or annually per ISM PMS. "
            "Wärtsilä W20 service manual specifies spray pattern check — all holes must have identical spray cone."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "generator",
            "source": "Wärtsilä W20 service manual; ISM Code 10.1",
            "topic": "injector_wear", "severity": "medium",
        },
    },
    {
        "id": "GEN-GOV-001",
        "text": (
            "Auxiliary generator governor instability and frequency deviation. "
            "Symptom pattern: frequency oscillates above/below 60 Hz (or 50 Hz) at steady load — hunting. "
            "Voltage fluctuates in synchrony with frequency variation. Load sharing imbalance when running "
            "parallel generators (one generator taking > 60% of combined load). "
            "Frequency deviation > ±2 Hz affects sensitive electronics and electric propulsion drives. "
            "Root cause: governor PID gain settings drifted (typically after fuel system maintenance), "
            "fuel rack sticking (mechanical governor), actuator response lag (electronic governor), "
            "injector wear causing variable fuel delivery, air in fuel system. "
            "Electronic governor (Woodward EG-3P/LSM): check gain and droop settings — typical droop 4–5%. "
            "Mechanical governor (Woodward UG-40): check oil level and viscosity, linkage wear. "
            "Action: frequency deviation > 1.5 Hz at rated load → investigate governor. "
            "If parallel operation affected, isolated generator operation until corrected. "
            "DNV class requirement: generators must maintain frequency within ±5% of rated (58–62 Hz or 47.5–52.5 Hz)."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "generator",
            "source": "Wärtsilä/MAN service manual; DNV Rules Pt.4 Ch.8; IEC 60092-301",
            "topic": "governor_fault", "severity": "high",
        },
    },
    {
        "id": "GEN-ALT-001",
        "text": (
            "Auxiliary generator alternator insulation degradation. "
            "Symptom pattern: insulation resistance drops progressively — measured with 500V/1000V megohmmeter. "
            "Normal IR > 100 MΩ (cold) or > 1 MΩ per kV of rated voltage. "
            "Warning: < 10 MΩ. Critical: < 1 MΩ — risk of flashover. "
            "Elevated winding temperature (> 80 °C at load) accelerates insulation ageing: "
            "Arrhenius rule — every 10 °C rise halves insulation life. "
            "Root cause: moisture ingress (port idle time, engine room flooding), oil contamination from "
            "crankcase vent, vibration causing insulation cracking, thermal cycling fatigue. "
            "DNV class survey requires IR test annually and polarisation index (PI = IR at 10 min / IR at 1 min). "
            "PI > 2.0 = good; PI 1.0–2.0 = marginal; PI < 1.0 = immediate attention required. "
            "Action: IR < 10 MΩ → dry winding in oven at 80 °C for 24 hours before re-measurement. "
            "If IR still < 10 MΩ after drying → winding replacement or rewinding required before return to service."
        ),
        "metadata": {
            "category": "failure_modes", "asset_type": "generator",
            "source": "DNV Rules Pt.4 Ch.8; IEC 60034-27-1; IEEE 43",
            "topic": "insulation_degradation", "severity": "critical",
        },
    },
]
