"""
Maritime regulatory requirements — ISM Code, SOLAS, MARPOL.
Sources: IMO instruments, official class society rules.
"""

REGULATIONS = [

    {
        "id": "REG-ISM-10",
        "text": (
            "ISM Code Section 10 — Maintenance of the Ship and Equipment. "
            "ISM Code 10.1: The company shall establish procedures to ensure that the ship is maintained "
            "in conformity with the provisions of the relevant rules and regulations and with any additional "
            "requirements established by the company. "
            "ISM Code 10.2: The company shall establish procedures to identify equipment and technical systems "
            "whose sudden operational failure may result in hazardous situations. The SMS shall provide for "
            "specific measures aimed at promoting the reliability of such equipment or systems. "
            "ISM Code 10.3: The company shall establish and maintain procedures to describe the system and "
            "how it is to be carried out, including measures to be taken in the case of deficiencies found. "
            "Non-conformity (NC) definition: Any observed situation where objective evidence indicates the "
            "non-fulfilment of a requirement. Major NC: An identifiable deviation posing a serious threat to "
            "the safety of personnel, the ship, or the environment. "
            "Annual ISM internal audit required. External ISM audit by flag state or recognised organisation "
            "every 2.5 years (Document of Compliance renewal every 5 years). "
            "Port State Control (PSC) inspections check ISM implementation — failure to maintain PMS records "
            "is grounds for deficiency notice or detention."
        ),
        "metadata": {
            "category": "regulations", "asset_type": "all",
            "source": "ISM Code (IMO Resolution A.741(18) as amended by MSC.273(85))",
            "topic": "ism_maintenance",
        },
    },
    {
        "id": "REG-SOLAS-START",
        "text": (
            "SOLAS II-1 Regulation 28 — Starting arrangements for main propulsion machinery. "
            "SOLAS II-1/28.3: Ships with main propulsion and associated machinery fitted with remote control "
            "from the navigation bridge shall have means to start the main propulsion machinery from a "
            "dead ship condition. "
            "SOLAS II-1/28.1: Starting air systems shall be capable of providing at least: "
            "12 consecutive starts for reversible main engines, 6 starts for non-reversible engines. "
            "SOLAS II-1/28.2: The air receivers for starting shall hold sufficient air for the required "
            "number of starts without recharging. Total receiver capacity typically 0.25–0.5 m³ at 30 bar "
            "depending on engine displacement. "
            "Compliance check: starting air compressor must charge receivers from atmospheric to 30 bar "
            "within a defined time (typically 30–45 minutes). "
            "A starting air compressor with volumetric efficiency < 55% or producing inadequate pressure "
            "represents a SOLAS violation — immediate major non-conformity. "
            "During PSC inspection, surveyor will check air receiver pressure and test starting arrangement. "
            "Class notation: DNV surveys starting air system under machinery class survey — annual test required."
        ),
        "metadata": {
            "category": "regulations", "asset_type": "compressor",
            "source": "SOLAS II-1 Chapter II-1 Regulation 28; DNV class requirements",
            "topic": "starting_air_compliance",
        },
    },
    {
        "id": "REG-SOLAS-POWER",
        "text": (
            "SOLAS II-1 Regulations 40–45 — Electrical power generation and emergency power. "
            "SOLAS II-1/40: Every ship shall have a main source of electrical power of sufficient capacity "
            "to supply all services necessary for safe operation. "
            "SOLAS II-1/42: Emergency source of electrical power — ships > 500 GT shall have an emergency "
            "generator capable of operating independently of the main power supply. "
            "Emergency generator requirements: automatically start and supply within 45 seconds of main power failure. "
            "Emergency generator must be capable of supplying: emergency lighting, navigational lights, "
            "communication equipment, fire detection and alarm systems, bilge pumps, sprinkler pumps. "
            "ISM non-conformity: auxiliary generator that cannot maintain voltage within ±6% and frequency "
            "within ±5% of rated values at rated load. "
            "DNV Rules Pt.4 Ch.8: generators must be tested for automatic start at each annual survey. "
            "Load test required: generator must accept 100% rated load without frequency drop > 10% transiently "
            "and must recover to steady-state within 5 seconds."
        ),
        "metadata": {
            "category": "regulations", "asset_type": "generator",
            "source": "SOLAS II-1 Regulations 40-45; DNV Rules Pt.4 Ch.8",
            "topic": "electrical_power_compliance",
        },
    },
    {
        "id": "REG-MARPOL-OIL",
        "text": (
            "MARPOL Annex I — Prevention of pollution by oil. "
            "Regulation 14: Oil filtering equipment — every ship of 400 GT and above shall be fitted with "
            "oil filtering equipment to ensure oily mixture discharged overboard does not exceed 15 ppm oil. "
            "Regulation 17: Oil Record Book Part I — every oil tanker and every ship of 400 GT and above "
            "shall maintain an Oil Record Book recording all oily water separator operations, bilge pumping, "
            "bunkering operations, and tank cleaning. "
            "Fuel oil purifier sludge: sludge produced by HFO purification must be collected in sludge tank "
            "and disposed of in port reception facility or through approved shipboard incinerator. "
            "Unlawful discharge of oily sludge overboard via bypass is a criminal offence. "
            "Maximum penalty in US: $500,000 per violation under APPS (Act to Prevent Pollution from Ships). "
            "PSC inspection: ORB (Oil Record Book) frequently checked — any false entries are grounds for "
            "detention and criminal prosecution of Master and Chief Engineer. "
            "Purifier operation: ensure sludge quantities in ORB are consistent with fuel consumption rates "
            "and separator operation hours."
        ),
        "metadata": {
            "category": "regulations", "asset_type": "purifier",
            "source": "MARPOL Annex I Regulations 14, 17; US APPS",
            "topic": "marpol_pollution_prevention",
        },
    },
    {
        "id": "REG-ISM-NC",
        "text": (
            "Port State Control inspection — common deficiency categories for machinery. "
            "Paris MOU and Tokyo MOU statistics: machinery-related deficiencies account for approximately "
            "25% of all PSC deficiencies. Top categories: "
            "1. Fire safety — engine room fire detection, fire dampers, CO2 system maintenance. "
            "2. Machinery — main engine, propulsion, starting air system deficiencies. "
            "3. Pollution prevention — ORB record-keeping, OWS certificate, sludge management. "
            "4. Safety of navigation — alarm systems, bridge equipment. "
            "5. ISM — SMS implementation, audit records, maintenance records not kept. "
            "Detention triggers for machinery: inability to start main engine, starting air below SOLAS minimum, "
            "emergency generator fails automatic start test, critical safety equipment (bilge pump, fire pump) "
            "not operational, major oil leak in machinery spaces. "
            "Pre-PSC inspection checklist: verify all safety valves are dated and tested within 12 months, "
            "check all alarm set-points against approved settings, verify PMS entries are up to date, "
            "ensure critical equipment test records are available."
        ),
        "metadata": {
            "category": "regulations", "asset_type": "all",
            "source": "Paris MOU; Tokyo MOU; ISM Code; SOLAS",
            "topic": "psc_inspection",
        },
    },
    {
        "id": "REG-VIBRATION",
        "text": (
            "ISO 10816-3 — Mechanical vibration, evaluation of machine vibration by measurements on non-rotating parts. "
            "Applicable to industrial machines with rated power above 15 kW and nominal speed 120–15,000 RPM. "
            "Marine machinery classification: "
            "Class I: Small machines (< 15 kW). "
            "Class II: Medium machines (15–75 kW, or up to 300 kW on rigid foundation). Includes auxiliary pumps. "
            "Class III: Large machines on rigid foundations (> 300 kW). Includes main pumps, compressors. "
            "Class IV: Turbomachinery on flexible foundations. "
            "Vibration severity zones (velocity RMS in mm/s): "
            "Zone A (new): Class II < 2.3 mm/s; Class III < 2.3 mm/s. "
            "Zone B (acceptable): Class II < 4.5 mm/s; Class III < 4.5 mm/s. "
            "Zone C (alarm — restricted operation): Class II < 7.1 mm/s; Class III < 7.1 mm/s. "
            "Zone D (danger — immediate shutdown): Class II > 7.1 mm/s; Class III > 11.2 mm/s. "
            "Trend monitoring: rate of change matters as much as absolute value. "
            "ISO 13373-1 recommends alert when vibration increases > 25% of Zone B limit in a single week."
        ),
        "metadata": {
            "category": "regulations", "asset_type": "all",
            "source": "ISO 10816-3:2009; ISO 13373-1",
            "topic": "vibration_standards",
        },
    },
]
