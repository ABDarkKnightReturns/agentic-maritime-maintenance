# Maritime PdM Demo — HF Data + ML Pipeline Architecture
## Version 3.0 · Design & Functionality Reference · 2026-05-19

---

## 1. END-TO-END ARCHITECTURE

```
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║        MV-EINDHOVEN ENGINE ROOM — DUAL-FREQUENCY AGENTIC AI PdM PLATFORM v2.0             ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────── LAYER 1: DUAL-MODE SIMULATOR ──────────────────────────────┐
│                                                                                             │
│  Each asset emits TWO data streams simultaneously:                                         │
│                                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  RT Mode  1 Hz · 6–8 tags per asset (process + vibration + efficiency)              │  │
│  │  HF Mode 10 Hz · 12 tags per asset (3-axis vib, shaft, temps, current, pressures)  │  │
│  └─────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                             │
│  PUMP-001    COMP-001    TURBO-001    PURIF-001    AUXGEN-001                               │
│  Health: BaseSimulator.health (0.0–1.0)                                                     │
│  Fault injection: inject_fault(severity) modifies physics model                             │
└──────────────┬────────────────────────────────────────────────────────────────┬────────────┘
               │ RT (1Hz)                                                        │ HF (10Hz)
               ▼                                                                 ▼
┌──────────────────────────────┐                              ┌──────────────────────────────┐
│  LAYER 2A: RT PIPELINE       │                              │  LAYER 2B: HF PIPELINE       │
│                              │                              │                              │
│  UNS Broker                  │                              │  HFStore (circular buffer)   │
│  └─ Harmonizer               │                              │  └─ Per-asset, per-tag       │
│      └─ CEP Engine           │                              │     deque(maxlen=6000)       │
│          ├─ Efficiency calc  │                              │     (10Hz × 600s = 10 min)   │
│          ├─ Vibration trend  │                              │                              │
│          ├─ Anomaly z-score  │                              │  Triggered extraction:       │
│          ├─ Health score     │                              │  get_window(asset, 120s)     │
│          └─ RUL estimate     │                              │  → pd.DataFrame              │
│                              │                              │                              │
│  AlarmManager                │                              │  On Watchkeeper alarm:       │
│  └─ Tier 1/2/3 thresholds   │                              │  capture_alarm_snapshot()    │
│  └─ trigger_queue            │                              │  (freezes 60s pre-alarm HF) │
└──────────────┬───────────────┘                              └──────────────┬───────────────┘
               │ alarm trigger                                               │ HF window data
               ▼                                                             ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: ML ANALYSIS PIPELINE  (runs in background thread on Watchkeeper alarm)         │
│                                                                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │FeatureExtractor │→ │AnomalyDetector  │→ │FaultClassifier  │→ │ RULEstimator    │    │
│  │                 │  │                 │  │                 │  │                 │    │
│  │ Statistical:    │  │ IsolationForest │  │ Rule-based +    │  │ Linear trend on │    │
│  │ · RMS, kurtosis │  │ fitted on       │  │ probabilistic   │  │ HF health proxy │    │
│  │ · crest factor  │  │ first 60s of    │  │                 │  │                 │    │
│  │ · peak-to-peak  │  │ healthy data    │  │ Fault classes:  │  │ Projects to     │    │
│  │ · skewness      │  │                 │  │ · bearing_wear  │  │ failure thresh  │    │
│  │                 │  │ anomaly_score   │  │ · cavitation    │  │                 │    │
│  │ Spectral (FFT): │  │ 0.0–1.0        │  │ · imbalance     │  │ rul_days +      │    │
│  │ · dominant_freq │  │ anomaly_flag    │  │ · misalignment  │  │ confidence      │    │
│  │ · spectral_RMS  │  │ (>0.65 = anom) │  │ · looseness     │  │ (R² based)      │    │
│  │ · band power    │  └─────────────────┘  │ · seal_leak     │  └─────────────────┘    │
│  │                 │                        │ · fouling       │                          │
│  │ Trend:          │                        │ · normal        │                          │
│  │ · slope (30s)   │                        │                 │                          │
│  │ · acceleration  │                        │ + probabilities │                          │
│  └─────────────────┘                        └─────────────────┘                          │
│                                   ▼                                                       │
│                         ┌─────────────────────────────────────────────┐                  │
│                         │  MLAnalysisResult (dataclass)               │                  │
│                         │  · anomaly_score, anomaly_detected          │                  │
│                         │  · fault_class, fault_probability           │                  │
│                         │  · fault_candidates (top 3)                 │                  │
│                         │  · rul_days, rul_confidence                 │                  │
│                         │  · dominant_frequency_hz                    │                  │
│                         │  · kurtosis, crest_factor, vibration_rms_hf │                 │
│                         │  · narrative (human-readable summary)       │                  │
│                         └─────────────────────────────────────────────┘                  │
│                                                                                           │
│  MLResultStore: stores latest result per asset_id (thread-safe)                          │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                              │ structured ML result
                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: AGENT CHAIN  (existing chain, Deep Diagnostics upgraded)                       │
│                                                                                           │
│  Watchkeeper ──────────────────────────────────────────────────────────────────────────  │
│  · Confirms alarm, cross-correlates sensors (unchanged)                                  │
│  · Passes trigger to cascade                                                             │
│          │                                                                               │
│          ▼                                                                               │
│  Deep Diagnostics  ◄── UPGRADED                                                         │
│  · NEW Tool: get_hf_analysis(asset_id, duration_s)                                      │
│    └─ Returns: ML result JSON + feature summary + narrative                              │
│  · Existing tools: get_asset_health, get_telemetry_trend, kb_retrieve                   │
│  · Claude now reasons over:                                                              │
│    [ML evidence] + [CEP metrics] + [KB standards] → root cause with confidence          │
│          │                                                                               │
│          ▼                                                                               │
│  Maintenance Planner ──► ISM Compliance ──► Fleet Intelligence  (unchanged)             │
│                                                                                           │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  LAYER 5: STREAMLIT UI  (new ML visibility panels)                                       │
│                                                                                           │
│  Fleet Overview Tab:                                                                     │
│  · HF buffer status indicator per asset (● live / ○ offline)                            │
│  · ML last-analysis timestamp                                                            │
│                                                                                           │
│  Incidents Tab — enhanced incident card:                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐               │
│  │  🧠 ML ANALYSIS RESULTS                                              │               │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │               │
│  │  │Anomaly Score │  │Fault Class   │  │HF RUL        │              │               │
│  │  │  78%  🔴     │  │bearing_wear  │  │21.4 days     │              │               │
│  │  │              │  │  prob: 0.82  │  │(medium conf) │              │               │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │               │
│  │  Dominant Freq: 142 Hz  Kurtosis: 7.3  Crest Factor: 5.1           │               │
│  │  ▶ ML Narrative + Feature Detail (expander)                         │               │
│  └──────────────────────────────────────────────────────────────────────┘               │
│                                                                                           │
│  Activity Feed:                                                                          │
│  🧠 ML Pipeline  PUMP-001  anomaly detected (score 0.78) · bearing_wear p=0.82          │
│                                                                                           │
│  Agent Chain Timeline:                                                                   │
│  🔭 Watchkeeper ✅  🧠 ML Analysis ✅  🔬 Deep Diagnostics ✅  📋 Planner ✅            │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. FULL FUNCTIONAL CALL CHAIN

Every function-to-function relationship from tick to work order creation:

```
app.py: _sim_loop() [daemon thread, 1Hz]
  └─ for sim in fleet.values():
      └─ sim.tick()  [BaseSimulator.tick()]
          └─ _generate_readings(ts) → dict[tag, float]
          └─ returns TelemetrySnapshot + list[UNSMessage]
      └─ broker.publish_many(messages)  [UNSBroker]
          └─ harmonizer.on_message(msg)  [Harmonizer]
              └─ cep_engine.on_message(asset_id, tag, value, ts)  [CEPEngine]
                  └─ asset_windows[asset_id].update(tag, value, ts)  [AssetWindow]

app.py: _hf_sim_loop() [daemon thread, 10Hz]
  └─ for sim in fleet.values():
      └─ sim.tick_hf()  [BaseSimulator.tick_hf()]
          └─ _generate_hf_readings(ts) → dict[tag, float]
          └─ returns list[HFSample]
      └─ hf_store.update(sample)  [HFStore]
          └─ _buffers[asset_id][tag].append(value)  ← deque(maxlen=6000)
  └─ ml_pipeline.try_fit_baselines()  [after 60s, once]
      └─ hf_store.get_window(asset_id, 60s) → pd.DataFrame
      └─ anomaly_detector.fit(asset_id, features_df)

CEPEngine._run() [daemon thread, wakes on UNS publish]
  └─ every 1.0s per asset: _compute_and_publish(asset_id)
      ├─ _compute_pump/compressor/turbo/purifier/generator(window)
      │   └─ efficiency calculations, derived metrics, thresholds
      ├─ _compute_universal(window)
      │   └─ vibration_rms = sqrt(mean(vib_x² + vib_y²))
      │   └─ anomaly_score (z-score based, 1Hz)
      ├─ _compute_health_score(metrics) → float 0–100
      │   └─ weighted penalty model (see Section 8)
      ├─ _estimate_rul(asset_id, health_score) → float days
      │   └─ linear degradation extrapolation
      └─ alarm_manager.evaluate(asset_id, metrics)  [AlarmManager]
          └─ for each threshold:
              └─ _check_threshold(asset_id, metric, value, threshold)
                  └─ if breach and not already_active:
                      └─ _maybe_trigger_watchkeeper(asset_id, metric, tier, ...)
                          ├─ hf_store.capture_alarm_snapshot(asset_id)
                          │   └─ _alarm_snapshots[asset_id] = HFSnapshot(get_window(60s))
                          └─ trigger_queue.put(trigger_dict)

app.py: _watchkeeper_loop() [daemon thread, blocks on trigger_queue.get()]
  └─ trigger = trigger_queue.get()
  └─ threading.Thread(target=_run_cascade, args=(trigger,...)).start()

app.py: _run_cascade(trigger, agents, wo_store, gen) [per-incident thread]
  ├─ incident_store.create_incident(trigger) → IncidentRecord (INC-YYYY-NNN)
  │
  ├─ [STEP 1] WatchkeeperAgent.run(trigger)
  │   └─ BaseAgent.run() → anthropic.messages.create() [with tool loop]
  │       tools: get_asset_health, get_telemetry_trend, get_recent_alerts,
  │              get_maintenance_history, get_fleet_overview, kb_retrieve
  │   └─ incident_store.complete_watchkeeper(inc_id, summary, tool_calls, full_output)
  │
  ├─ [STEP 2] ML Pipeline (Python, no LLM)
  │   └─ ml_pipeline.analyze(asset_id, asset_type, duration_s=120)
  │       ├─ hf_store.get_alarm_snapshot(asset_id) → pd.DataFrame (120s × 10Hz)
  │       ├─ feature_extractor.extract(df, asset_type) → dict[feature, value]
  │       ├─ anomaly_detector.score(asset_id, features) → float 0–1
  │       ├─ fault_classifier.classify(features, asset_type)
  │       │   → (fault_class, probability, candidates)
  │       ├─ rul_estimator.estimate(features, cep_health, cep_rul)
  │       │   → (rul_days, confidence, trend_slope)
  │       └─ _build_narrative(result) → str
  │   └─ incident_store.complete_ml_analysis(inc_id, ml_result)
  │
  ├─ [STEP 3] DeepDiagnosticsAgent.run(trigger + ml_context)
  │   └─ BaseAgent.run() → anthropic.messages.create() [with tool loop]
  │       tools: get_hf_analysis (FIRST), get_asset_health, get_telemetry_trend,
  │              get_recent_alerts, get_maintenance_history, kb_retrieve
  │       get_hf_analysis → ml_pipeline.get_latest(asset_id) → MLAnalysisResult JSON
  │   └─ incident_store.complete_diagnostics(inc_id, summary, tool_calls, full_output)
  │
  ├─ [STEP 4] MaintenancePlannerAgent.run(trigger)
  │   └─ BaseAgent.run() → anthropic.messages.create() [with tool loop]
  │       tools: get_asset_health, get_maintenance_history, create_work_order,
  │              get_spare_parts, get_port_schedule, kb_retrieve
  │       create_work_order → wo_store.create() → WO-YYYY-NNN
  │   └─ incident_store.complete_planner(inc_id, summary, wo_id, tool_calls, full_output)
  │
  ├─ [TIER 3 ONLY — parallel threads]
  │   ├─ ISMComplianceAgent.run(trigger)
  │   │   └─ tools: get_asset_health, kb_retrieve (SOLAS/ISM), get_maintenance_history
  │   │   └─ incident_store.complete_compliance(inc_id, summary, status, ...)
  │   │
  │   └─ FleetIntelligenceAgent.run(trigger)
  │       └─ tools: get_fleet_overview, get_asset_health, kb_retrieve
  │       └─ incident_store.complete_fleet_intel(inc_id, advisory, ...)
  │
  └─ IncidentRecord.chain_complete → True → status = "Chain Complete"
```

---

## 3. THREAD ARCHITECTURE & APP INITIALIZATION

```
app.py startup sequence:
  1. _init_stack() — called once via st.session_state guard
     ├─ fleet = {PUMP-001: PumpSim, COMP-001: CompSim, ...}
     ├─ broker = UNSBroker()
     ├─ harmonizer = Harmonizer(broker)
     ├─ cep_engine = CEPEngine(broker)  → starts its own daemon thread
     ├─ alarm_manager = AlarmManager(cep_engine, trigger_queue)
     ├─ hf_store = HFStore()
     ├─ ml_pipeline = MLPipeline(hf_store)
     ├─ wo_store = WorkOrderStore()
     └─ threading.Thread(target=_sim_loop).start()       [RT, 1Hz]
        threading.Thread(target=_hf_sim_loop).start()    [HF, 10Hz]
        threading.Thread(target=_watchkeeper_loop).start()[cascade trigger]

  2. Four permanent daemon threads (always running):
     ┌──────────────────┬──────────────┬─────────────────────────────────────┐
     │ Thread           │ Rate         │ Responsibility                      │
     ├──────────────────┼──────────────┼─────────────────────────────────────┤
     │ _sim_loop        │ 1Hz          │ RT simulation → UNS → CEP          │
     │ _hf_sim_loop     │ 10Hz         │ HF simulation → HFStore + ML fit   │
     │ CEPEngine._run   │ continuous   │ metric computation + alarm eval     │
     │ _watchkeeper_loop│ event-driven │ drains trigger_queue                │
     └──────────────────┴──────────────┴─────────────────────────────────────┘

  3. Per-incident cascade threads (spawned on alarm):
     ├─ One thread per incident — sequential agent calls within thread
     ├─ Tier 3: compliance + fleet_intel run as parallel sub-threads
     └─ Thread terminates when chain_complete = True

  4. Streamlit re-render loop (auto-refresh, every ~1s via st_autorefresh):
     └─ Reads shared state: cep_engine.metrics, incident_store, wo_store, hf_store
     └─ All state access is thread-safe (threading.Lock in each store)
```

---

## 4. DATA FLOW — ALARM TO ROOT CAUSE

```
t=0s   Simulator (PUMP-001) tick_hf() → HFStore.update()  [every 100ms]
t=0s   Simulator (PUMP-001) tick()    → CEP Engine         [every 1s]

t=30s  CEP: bearing_temp_c = 78.80°C > alarm threshold (78.0°C)
       AlarmManager.evaluate() → fires alarm
       AlarmManager._maybe_trigger_watchkeeper() → trigger_queue.put(trigger)
       HFStore.capture_alarm_snapshot("PUMP-001")  ← freeze HF buffer now

t=31s  _watchkeeper_loop drains trigger_queue
       → spawns _run_cascade(trigger, agents, wo_store, gen)

t=31s  [CASCADE THREAD]
       incident_store.create_incident(trigger) → INC-2026-001

t=32s  Watchkeeper agent runs (~16s)
       → confirms breach, cross-correlates, raises alert

t=48s  [ML Pipeline runs — pure Python, ~2–3s]
       ml_pipeline.analyze("PUMP-001", "Pump", duration_s=120)
       ├── HFStore.get_alarm_snapshot() → 120s × 10Hz = 1200 samples
       ├── FeatureExtractor.extract(df, "Pump")
       │   ├── vib_rms=4.8, kurtosis=7.3, crest_factor=5.1
       │   ├── dominant_freq=142Hz, spectral_centroid=98Hz
       │   └── bearing_temp_delta=+12°C
       ├── AnomalyDetector.score() → 0.78 (ANOMALY DETECTED)
       ├── FaultClassifier.classify()
       │   → bearing_wear (p=0.82), misalignment (p=0.11), normal (p=0.07)
       ├── RULEstimator.estimate() → 21.4 days, "medium", slope=-1.2/hr
       └── MLAnalysisResult saved to ml_pipeline._result_store

t=50s  Deep Diagnostics agent starts (~25s)
       Tool 1: get_hf_analysis("PUMP-001")   ← ML evidence, MANDATORY FIRST
               → returns MLAnalysisResult as structured JSON + narrative
       Tool 2: get_asset_health("PUMP-001")
       Tool 3: get_telemetry_trend("PUMP-001", "bearing_temp_c", ...)
       Tool 4: kb_retrieve("bearing wear kurtosis PUMP-001 failure mode")
       Tool 5: get_maintenance_history("PUMP-001")
       Claude: [ML says bearing_wear p=0.82 + kurtosis=7.3 + dominant 142Hz]
               + [CEP: health=57%, efficiency=57.3%, vibration RMS=4.8]
               + [KB: ISO 10816-3 bearing defect freq, OEM manual]
               → ROOT CAUSE: "Bearing race spalling. kurtosis 7.3 (>4 = defect
                 indicator per ISO 13373-3). 142 Hz dominant = 3.5× shaft freq
                 consistent with BPFI at rated speed. 21-day RUL (medium conf)."

t+N   Planner creates WO → [Tier 3: Compliance + Fleet Intel run in parallel]
```

---

## 5. RT TAGS PER ASSET (1 Hz)

These are the live sensor tags published to UNS and consumed by CEP Engine.

### PUMP-001 (Lube Oil Pump) — 7 RT tags
| Tag | Unit | CEP Use |
|-----|------|---------|
| discharge_pressure_bar | bar | pressure differential, efficiency |
| suction_pressure_bar | bar | cavitation detection |
| flow_rate_m3h | m³/h | pump efficiency calculation |
| motor_current_a | A | load monitoring, efficiency |
| bearing_temp_c | °C | **alarm trigger** (Warn 65°C / Alarm 78°C) |
| vibration_x_mms | mm/s | vibration_rms composite |
| vibration_y_mms | mm/s | vibration_rms composite |

**CEP Derived:** pump_efficiency (%), vibration_rms (mm/s), health_score (0–100), rul_days, bearing_wear_index

### COMP-001 (Starting Air Compressor) — 7 RT tags
| Tag | Unit | CEP Use |
|-----|------|---------|
| inlet_pressure_bar | bar | volumetric efficiency |
| outlet_pressure_bar | bar | compression ratio, efficiency |
| inlet_temp_c | °C | thermodynamic efficiency |
| outlet_temp_c | °C | heat of compression |
| motor_current_a | A | load, power efficiency |
| oil_pressure_bar | bar | lubrication health |
| vibration_mms | mm/s | vibration_rms |

**CEP Derived:** volumetric_efficiency (%), compression_ratio, health_score, rul_days

### TURBO-001 (Turbocharger) — 6 RT tags
| Tag | Unit | CEP Use |
|-----|------|---------|
| speed_rpm | RPM | turbo efficiency, surge margin |
| boost_pressure_bar | bar | turbo efficiency, surge margin |
| exhaust_temp_in_c | °C | turbine inlet temperature |
| exhaust_temp_out_c | °C | turbine efficiency calculation |
| lube_oil_pressure_bar | bar | bearing lubrication health |
| vibration_mms | mm/s | vibration_rms |

**CEP Derived:** turbo_efficiency (%), surge_margin (%), health_score, rul_days

### PURIF-001 (Fuel Oil Purifier) — 6 RT tags
| Tag | Unit | CEP Use |
|-----|------|---------|
| bowl_speed_rpm | RPM | bowl speed deviation (alarm if >4% from nominal) |
| feed_temp_c | °C | separation efficiency |
| back_pressure_bar | bar | separation quality, bowl health |
| motor_current_a | A | load monitoring |
| vibration_mms | mm/s | vibration_rms |
| sludge_discharge_count | count | sludge cycle frequency |

**CEP Derived:** bowl_speed_deviation (%), purifier_efficiency (%), health_score, rul_days

### AUXGEN-001 (Auxiliary Generator) — 8 RT tags
| Tag | Unit | CEP Use |
|-----|------|---------|
| frequency_hz | Hz | frequency deviation (Warn ±1.5Hz / Alarm ±2.5Hz) |
| voltage_v | V | voltage regulation |
| load_kw | kW | load factor |
| exhaust_temp_c | °C | combustion health |
| coolant_temp_c | °C | cooling system health |
| lube_oil_pressure_bar | bar | lubrication health |
| fuel_consumption_lh | L/h | fuel efficiency |
| vibration_mms | mm/s | vibration_rms |

**CEP Derived:** frequency_deviation (Hz), load_factor (%), fuel_efficiency (L/kWh), health_score, rul_days

---

## 6. HF TAGS PER ASSET (10 Hz — 12 tags each)

### PUMP-001 (Lube Oil Pump)
| Tag | Unit | Purpose |
|-----|------|---------|
| vib_x_hf | mm/s | X-axis radial vibration |
| vib_y_hf | mm/s | Y-axis radial vibration |
| vib_z_hf | mm/s | Axial vibration |
| bearing_temp_hf | °C | Bearing housing temperature |
| motor_current_hf | A | Motor phase current |
| discharge_pressure_hf | bar | Pump discharge |
| suction_pressure_hf | bar | Pump suction |
| flow_rate_hf | m³/h | Actual flow |
| shaft_speed_hf | RPM | Shaft rotational speed |
| motor_temp_hf | °C | Motor winding temperature |
| seal_leakage_hf | ml/min | Mechanical seal leakage rate |
| outlet_temp_hf | °C | Fluid outlet temperature |

### COMP-001 (Starting Air Compressor)
| Tag | Unit | Purpose |
|-----|------|---------|
| vib_radial_hf | mm/s | Radial vibration |
| vib_axial_hf | mm/s | Axial vibration |
| motor_current_hf | A | Phase current |
| inlet_pressure_hf | bar | Inlet pressure |
| outlet_pressure_hf | bar | Outlet pressure |
| inlet_temp_hf | °C | Inlet temperature |
| outlet_temp_hf | °C | Outlet/discharge temperature |
| shaft_speed_hf | RPM | Shaft speed |
| valve_click_hf | count/s | Valve impact count (valve wear) |
| motor_temp_hf | °C | Motor temperature |
| lube_oil_pressure_hf | bar | Lube oil pressure |
| vib_z_hf | mm/s | Z-axis vibration |

### TURBO-001 (Turbocharger)
| Tag | Unit | Purpose |
|-----|------|---------|
| vib_radial_hf | mm/s | Radial vibration |
| vib_axial_hf | mm/s | Axial vibration |
| rotor_speed_hf | RPM | Turbine rotor speed |
| exhaust_in_temp_hf | °C | Turbine inlet temperature |
| exhaust_out_temp_hf | °C | Turbine outlet temperature |
| boost_pressure_hf | bar | Compressor boost pressure |
| compressor_inlet_temp_hf | °C | Compressor inlet |
| turbine_inlet_temp_hf | °C | Turbine inlet |
| lube_oil_pressure_hf | bar | Bearing lube oil pressure |
| lube_oil_temp_hf | °C | Lube oil temperature |
| bearing_temp_de_hf | °C | Drive-end bearing temperature |
| bearing_temp_fe_hf | °C | Free-end bearing temperature |

### PURIF-001 (Fuel Oil Purifier)
| Tag | Unit | Purpose |
|-----|------|---------|
| vib_radial_hf | mm/s | Radial vibration |
| vib_axial_hf | mm/s | Axial vibration |
| bowl_speed_hf | RPM | Bowl rotational speed |
| motor_current_hf | A | Drive motor current |
| feed_flow_hf | L/h | Feed flow rate |
| feed_temp_hf | °C | Feed temperature |
| back_pressure_hf | bar | Back pressure |
| sludge_pressure_hf | bar | Sludge space pressure |
| motor_temp_hf | °C | Motor temperature |
| frame_vib_hf | mm/s | Frame / base vibration |
| op_water_pressure_hf | bar | Operating water pressure |
| discharge_temp_hf | °C | Discharge temperature |

### AUXGEN-001 (Auxiliary Generator)
| Tag | Unit | Purpose |
|-----|------|---------|
| vib_radial_hf | mm/s | Radial vibration |
| vib_axial_hf | mm/s | Axial vibration |
| shaft_speed_hf | RPM | Engine/generator speed |
| load_kw_hf | kW | Electrical load (high-res) |
| frequency_hf | Hz | Output frequency (governor analysis) |
| voltage_hf | V | Terminal voltage |
| current_hf | A | Output current |
| exhaust_temp_hf | °C | Exhaust gas temperature |
| jacket_water_temp_hf | °C | Jacket water temperature |
| lube_oil_pressure_hf | bar | Lube oil pressure |
| fuel_rack_hf | % | Fuel rack position (governor actuator) |
| turbo_speed_hf | RPM | Turbocharger speed |

---

## 7. COMPLETE ALARM THRESHOLD TABLE

All thresholds configured in `pipeline/alarm_manager.py`.

| Asset | Metric | Warning | Alarm | Tier | Compliance |
|-------|--------|---------|-------|------|------------|
| PUMP-001 | bearing_temp_c | 65°C | 78°C | 2 | — |
| PUMP-001 | pump_efficiency | 75% | 65% | 2 | — |
| PUMP-001 | bearing_wear_index | — | 0.5 | 2 | — |
| PUMP-001 | pump_efficiency (critical) | — | 55% | 3 | ISM-10.1 |
| COMP-001 | volumetric_efficiency (warn) | 65% | — | 2 | — |
| COMP-001 | volumetric_efficiency (alarm) | — | 55% | 2 | — |
| COMP-001 | volumetric_efficiency (SOLAS) | — | 45% | 3 | SOLAS-II-1/28 |
| TURBO-001 | turbo_efficiency | 60% | 50% | 2 | — |
| TURBO-001 | surge_margin | 40% | 20% | 3 | SOLAS-II-2 |
| PURIF-001 | bowl_speed_deviation | 4% | 7% | 2 | — |
| PURIF-001 | purifier_efficiency | 70% | 55% | 2 | — |
| AUXGEN-001 | frequency_deviation | 1.5 Hz | 2.5 Hz | 2 | — |
| AUXGEN-001 | load_factor | — | 95% | 2 | — |
| ALL | vibration_rms | 4.5 mm/s | 7.1 mm/s | 2 | ISO 10816-3 |
| ALL | health_score | — | 30 | 2→3 | ISM |

**Tier definitions:**
- Tier 1: Monitor only — no agent chain triggered
- Tier 2: Investigate — Watchkeeper → ML Analysis → Deep Diagnostics → Planner (4 agents)
- Tier 3: Critical/SOLAS — same as Tier 2 + ISM Compliance + Fleet Intelligence (6 agents)

**AlarmManager state machine:** Each (asset, metric) pair is tracked independently. A Tier 2 alarm fires once per fault (re-arms only after recovery). Tier 3 overrides active Tier 2.

---

## 8. CEP HEALTH SCORE MODEL

Health score (0–100) computed in `cep_engine._compute_health_score()` using a weighted penalty model.

```
health_score = 100 − Σ(penalty_i × weight_i)

Penalties applied when metric exceeds warning threshold:
  ┌──────────────────────────────┬────────┬────────────────────────────┐
  │ Metric                       │ Weight │ Penalty rule               │
  ├──────────────────────────────┼────────┼────────────────────────────┤
  │ vibration_rms                │ 0.30   │ linear from warn→alarm     │
  │ primary efficiency metric    │ 0.25   │ linear from warn→alarm     │
  │ bearing_temp / exhaust_temp  │ 0.20   │ linear from warn→alarm     │
  │ secondary process metric     │ 0.15   │ step at warning threshold  │
  │ lube_oil_pressure / other    │ 0.10   │ step at warning threshold  │
  └──────────────────────────────┴────────┴────────────────────────────┘

Clamp: health_score = max(0, min(100, computed))

RUL estimation (CEP, 1Hz basis):
  slope = linear regression of health_score over last 30 data points
  rul_hours = (health_score − 0) / abs(slope_per_hour)
  rul_days = rul_hours / 24
  If slope ≥ 0 (improving/stable): rul_days = 999 (no degradation)
```

---

## 9. ML PIPELINE ALGORITHM DETAIL

### 9.1 Feature Extraction
Input: pd.DataFrame with columns = HF tags, index = timestamp (120s × 10Hz = 1200 rows)

**Statistical features** (applied to primary vibration tag):
- `mean`, `std`, `min`, `max`
- `rms` = sqrt(mean(x²))
- `peak_to_peak` = max - min
- `kurtosis` (scipy) — bearing defect indicator (>4 = warning, >8 = severe)
- `skewness` (scipy) — asymmetry in signal distribution
- `crest_factor` = peak / rms — impulsiveness (>6 = warning)
- `shape_factor` = rms / mean(|x|)
- `impulse_factor` = peak / mean(|x|)

**Spectral features** (FFT on vibration, fs=10 Hz):
- `dominant_frequency_hz` = argmax(|FFT|)
- `spectral_rms` = sqrt(sum(|FFT|²) / N)
- `spectral_centroid_hz` = sum(freq × |FFT|) / sum(|FFT|)
- `sub_sync_power` = power at 0–0.4× running_freq (looseness)
- `sync_power` = power at 0.8–1.2× running_freq (imbalance)
- `2x_sync_power` = power at 1.7–2.3× running_freq (misalignment)
- `high_freq_power` = power > 3× running_freq (bearing defect)

**Trend features**:
- `vib_trend_slope` = linear regression slope over window (mm/s per hour)
- `temp_delta` = bearing_temp[-1] - bearing_temp[0] (°C rise in window)
- `efficiency_slope` = efficiency trend slope

### 9.2 Isolation Forest (Anomaly Detection)
- Library: `sklearn.ensemble.IsolationForest`
- `n_estimators=100`, `contamination=0.1`, `random_state=42`
- **Fitting**: On first 60 seconds of data after app start (assumed healthy baseline).
  If insufficient data, use synthetic normal data generated from simulator healthy params.
- **Scoring**: `decision_function()` output mapped to 0–1 anomaly score
  (score=-1 from sklearn → 1.0 anomaly; score=+1 → 0.0 anomaly)
- **Feature vector**: [rms, kurtosis, crest_factor, dominant_freq,
  spectral_centroid, sub_sync_power, 2x_sync_power, high_freq_power,
  temp_delta, vib_trend_slope]
- **Threshold**: anomaly_score > 0.65 → anomaly_detected = True

### 9.3 Fault Classification (Rule-Based Probabilistic)
Scores each fault class using physics-informed rules, then normalizes to probabilities.

| Fault | Key indicators | Primary sensors |
|-------|----------------|-----------------|
| bearing_wear | kurtosis>4, crest_factor>5, high_freq_power↑, temp_delta>5 | vib, bearing_temp |
| cavitation | pressure_fluctuation↑, vib broadband↑, >2×freq | pressure, vib |
| imbalance | sync_power dominant, vib_rms moderate, smooth spectrum | vib |
| misalignment | 2×sync_power↑, axial_vib↑, bearing_temp mild↑ | vib_radial, vib_axial |
| looseness | sub_sync_power↑, multiple harmonics, vib asymmetric | vib |
| seal_leak | flow drop, pressure drop, vib normal | flow, pressure |
| fouling | efficiency↓, temp↑, vib normal/mild | efficiency, temp |
| normal | all scores low | — |

### 9.4 RUL Estimation
1. Extract health proxy series from HF window:
   `health_proxy = 1 - normalize(vib_rms_series, alarm_threshold=7.1)`
2. Fit linear regression on health proxy (30-point rolling, last 60s)
3. Project: `rul_hours = (health_proxy[-1] - 0.0) / abs(slope_per_hour)`
4. `rul_days = rul_hours / 24`
5. Confidence based on R²: >0.85 = high, >0.6 = medium, else low
6. Take `min(hf_rul, cep_rul)` — most conservative estimate wins

---

## 10. UI TABS — FULL FUNCTIONALITY REFERENCE

### Tab 1: Fleet Overview
**What it shows:** Top-level operational picture — one card per asset.

| Element | Source | Purpose |
|---------|--------|---------|
| Asset health card (0–100) | CEPEngine.health_score | Quick condition triage |
| Health trend arrow | last 5 CEP health values | Improving / stable / degrading |
| Active alarm count | AlarmManager.active_alarms | Urgent attention indicator |
| HF buffer indicator (● / ○) | HFStore.get_buffer_status() | Shows HF data is live |
| Last ML analysis badge | MLPipeline.get_latest() | "bearing_wear · 14m ago" |
| Fleet summary bar | aggregate of all assets | Healthy / Warning / Critical count |
| Demo controls | inject_fault(), reset() | For demo presentations |

**Who uses it:** Any officer doing a quick scan. Chief Engineer for morning rounds.

---

### Tab 2: Live Telemetry
**What it shows:** Real-time sensor charts and CEP-derived metrics per asset.

| Element | Source | Purpose |
|---------|--------|---------|
| RT sensor charts (6–8 per asset) | UNS broker stream | 60-point rolling chart |
| CEP derived metrics table | CEPEngine output | Efficiency, RUL, health |
| Alarm status per metric | AlarmManager | Red/amber/green color coding |
| Current value vs. threshold | AlarmManager thresholds | Margin visibility |

**Who uses it:** Watch officer monitoring live conditions. Engineer investigating a specific parameter trend.

---

### Tab 3: Agent Console (On-Demand Analysis)
**What it shows:** Manual agent execution panel — chief engineer initiates analysis outside the alarm chain.

**Why it still exists after the automated cascade:**
The alarm chain handles *reactive* responses — an alarm fires, agents run. The Agent Console handles *proactive* use cases that a chief engineer initiates:

| Proactive use case | How used |
|--------------------|----------|
| Pre-departure check | Run diagnostics on all assets before sailing — confirm no latent faults |
| Borderline asset investigation | Asset health = 68%, no alarm yet — chief wants analysis now |
| Post-repair verification | After maintenance — run diagnostics to confirm repair was effective |
| Voyage planning input | Assess fleet condition before a long passage, check spare parts |
| Training & familiarisation | New officer learning the system — explore agent outputs interactively |

**Functional mechanics:**
- Select agent (Watchkeeper / Deep Diagnostics / Maintenance Planner / Fleet Intel)
- Select target asset (or "fleet-wide")
- Free-text context input (e.g., "Check bearing condition post shaft seal replacement")
- Agent runs on-demand — output shown in console panel
- **Not persisted to IncidentRecord** — this is exploratory, not an alarm-driven audit trail
- Results do not create Work Orders (unless planner explicitly called with intent)

**Chief Engineer verdict:** Keep the tab. It serves a distinct proactive workflow that alarm automation cannot replace. Recommended enhancement: add a "Save to Incident" button to link a manual analysis to an existing incident.

---

### Tab 4: Work Orders
**What it shows:** All work orders created by the Maintenance Planner agent.

| Element | Source | Purpose |
|---------|--------|---------|
| WO cards (WO-YYYY-NNN) | WorkOrderStore | Shows asset, fault, recommended action |
| Priority badge | Planner output | Immediate / Next Port / 30 Days |
| Approve / Reject buttons | wo_store.update_status() | Chief Engineer decision gate |
| Status lifecycle | Open → Approved / Rejected | Audit trail |
| Link to incident | wo_id in IncidentRecord | Trace WO back to originating alarm |

**Who uses it:** Chief Engineer approving/rejecting maintenance recommendations. Port Engineer planning dry-dock scope.

---

### Tab 5: Incidents
**What it shows:** Full audit trail for every alarm-triggered agent chain.

| Element | Source | Purpose |
|---------|--------|---------|
| Incident header (INC-YYYY-NNN) | IncidentStore | ID, asset, metric, timestamp |
| Tier badge | trigger.tier | TIER 2 orange / TIER 3 red |
| Trigger value vs. threshold | trigger dict | Context: what breached what |
| Agent chain timeline | IncidentRecord.steps | 🔭→🧠→🔬→📋→⚖️→🌐 with status |
| Step duration | AgentStep.duration_s | Performance visibility |
| 🧠 ML Analysis panel | IncidentRecord.ml_result | Anomaly score, fault class, RUL, kurtosis |
| ML narrative expander | ml_result.narrative | Full feature interpretation |
| Full agent output expanders | AgentStep.full_output | Complete reasoning per agent |
| Compliance status | IncidentRecord.compliance_status | COMPLIANT / MINOR NC / MAJOR NC |
| Fleet advisory | IncidentRecord.fleet_advisory | Cross-fleet pattern warning |
| Resolve button | incident_store.resolve_incident() | Marks incident closed |

**Who uses it:** Chief Engineer reviewing AI reasoning. Superintendent auditing compliance. Port Captain checking SOLAS status.

---

## 11. CLASS DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────┐
│  simulator/base_simulator.py  (MODIFIED)                                │
│                                                                         │
│  class BaseSimulator (abstract)                                         │
│  ├── tick() → (TelemetrySnapshot, list[UNSMessage])    [existing, RT]  │
│  ├── tick_hf() → list[HFSample]                        [NEW, 10Hz]     │
│  ├── _generate_readings(ts) → dict[str,float]          [existing]      │
│  └── _generate_hf_readings(ts) → dict[str,float]       [NEW, abstract] │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  storage/hf_store.py  (NEW)                                             │
│                                                                         │
│  @dataclass HFSample                                                    │
│  ├── asset_id: str                                                      │
│  ├── timestamp: datetime                                                │
│  └── readings: dict[str, float]   # 12 tags at this instant            │
│                                                                         │
│  class HFStore                                                          │
│  ├── _buffers: dict[str, dict[str, deque]]  # [asset][tag] → deque     │
│  │   maxlen = HF_RATE × HF_WINDOW_S = 10 × 600 = 6000                 │
│  ├── _lock: threading.Lock                                              │
│  ├── _alarm_snapshots: dict[str, HFSnapshot]  # frozen on alarm        │
│  │                                                                      │
│  ├── update(sample: HFSample) → None                                   │
│  ├── get_window(asset_id, duration_s=120) → pd.DataFrame               │
│  ├── capture_alarm_snapshot(asset_id) → None  # freeze last 60s        │
│  ├── get_alarm_snapshot(asset_id) → pd.DataFrame | None                │
│  ├── get_buffer_status() → dict[str, dict]  # sample counts            │
│  └── clear(asset_id=None) → None                                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  ml/models.py  (NEW)                                                    │
│                                                                         │
│  @dataclass MLAnalysisResult                                            │
│  ├── asset_id, asset_type, analyzed_at, window_duration_s, sample_count│
│  ├── anomaly_score: float          # 0.0–1.0                           │
│  ├── anomaly_detected: bool        # score > 0.65                      │
│  ├── fault_class: str              # bearing_wear/cavitation/etc       │
│  ├── fault_probability: float                                           │
│  ├── fault_candidates: list[dict]  # top 3 [{class, prob}]            │
│  ├── rul_days: float                                                    │
│  ├── rul_confidence: str           # high/medium/low                   │
│  ├── rul_trend_slope: float                                             │
│  ├── vibration_rms_hf: float                                            │
│  ├── dominant_frequency_hz: float                                       │
│  ├── kurtosis: float               # >4=warn, >8=severe               │
│  ├── crest_factor: float           # >6=warn                          │
│  ├── spectral_centroid_hz: float                                        │
│  ├── bearing_temp_delta: float                                          │
│  ├── feature_detail: dict          # full features for UI expander     │
│  └── narrative: str                # human-readable for Claude         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  ml/pipeline.py  (NEW) — orchestrator                                   │
│                                                                         │
│  class MLPipeline                                                       │
│  ├── hf_store, extractor, anomaly_detector, fault_classifier,          │
│  │   rul_estimator, _result_store, _lock                               │
│  ├── analyze(asset_id, asset_type, duration_s=120,                     │
│  │          cep_health=None, cep_rul=None) → MLAnalysisResult          │
│  ├── get_latest(asset_id) → MLAnalysisResult | None                    │
│  ├── run_baseline_fit(asset_id, asset_type) → None                     │
│  └── _build_narrative(result) → str                                    │
│                                                                         │
│  # Module-level singleton                                               │
│  ml_pipeline: MLPipeline                                               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  models/incident.py  (MODIFIED)                                         │
│                                                                         │
│  @dataclass AgentStep                                                   │
│  ├── agent_name, icon, label                                            │
│  ├── started_at, completed_at, tool_calls                               │
│  ├── summary: str       # one-line for dossier                         │
│  ├── full_output: str   # complete reasoning, no truncation            │
│  └── status: str        # pending/running/done/skipped                 │
│                                                                         │
│  @dataclass IncidentRecord                                              │
│  ├── incident_id, asset_id, metric, tier, compliance_code              │
│  ├── triggered_at, trigger_value, trigger_threshold, trigger_unit      │
│  ├── steps: dict[str, AgentStep]   # watchkeeper/ml_analysis/          │
│  │                                 # diagnostics/planner/compliance/   │
│  │                                 # fleet_intel                       │
│  ├── wo_id, compliance_status, fleet_advisory                          │
│  ├── status: str        # Open/Pending WO Approval/Chain Complete/     │
│  │                      # Resolved                                     │
│  └── ml_result: Optional[MLAnalysisResult]  # NEW                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 12. NEW FILES & MODIFICATIONS

### New Files
```
ml/
├── __init__.py
├── models.py              # MLAnalysisResult dataclass
├── feature_extractor.py   # Statistical + spectral (FFT) feature extraction
├── anomaly_detector.py    # Isolation Forest anomaly detection
├── fault_classifier.py    # Rule-based probabilistic fault classification
├── rul_estimator.py       # HF trend-based RUL estimation
└── pipeline.py            # Orchestrator + module-level singleton

storage/
└── hf_store.py            # Circular HF buffer (deque, thread-safe)
```

### Modified Files
```
simulator/base_simulator.py        + tick_hf(), _generate_hf_readings() abstract
simulator/pump_simulator.py        + _generate_hf_readings() — 12 tags at 10Hz
simulator/compressor_simulator.py  + _generate_hf_readings()
simulator/turbo_simulator.py       + _generate_hf_readings()
simulator/purifier_simulator.py    + _generate_hf_readings()
simulator/generator_simulator.py   + _generate_hf_readings()

pipeline/alarm_manager.py          + call HFStore.capture_alarm_snapshot() on alarm fire

agents/tools.py                    + TOOL_GET_HF_ANALYSIS schema
                                   + execute_tool handler for get_hf_analysis

agents/diagnostics.py              + add TOOL_GET_HF_ANALYSIS to tools list
                                   + update system prompt to use ML evidence

models/incident.py                 + ml_result: MLAnalysisResult | None field
pipeline/incident_store.py         + complete_ml_analysis() method

app.py                             + HFStore init + HF sim loop (10Hz thread)
                                   + ml_pipeline init + baseline fit
                                   + ML step in cascade (_run_cascade)
                                   + ML results panel in Incidents tab
                                   + HF buffer status in Fleet Overview
                                   + Activity Feed entry for ML pipeline
```

---

## 13. SCOPE METRICS

| Component | New/Modified | Lines (approx) |
|-----------|-------------|----------------|
| HFStore (circular buffer) | New | ~120 |
| 5× HF simulator methods | Modified | ~200 |
| FeatureExtractor (stats + FFT) | New | ~150 |
| AnomalyDetector (Isolation Forest) | New | ~80 |
| FaultClassifier (rule-based) | New | ~180 |
| RULEstimator (HF trend) | New | ~80 |
| MLPipeline (orchestrator) | New | ~120 |
| agents/tools.py (get_hf_analysis) | Modified | ~40 |
| agents/diagnostics.py | Modified | ~30 |
| models/incident.py | Modified | ~10 |
| pipeline/incident_store.py | Modified | ~20 |
| pipeline/alarm_manager.py | Modified | ~15 |
| app.py (HF loop + ML UI) | Modified | ~150 |
| **Total new Python** | — | **~1,200 lines** |

**Assets monitored:** 5
**RT tags total:** 34 (avg 6.8/asset)
**HF tags total:** 60 (12/asset)
**Agent chain (Tier 2):** 4 agents
**Agent chain (Tier 3):** 6 agents
**ML pipeline steps:** 4 (extract → detect → classify → RUL)
**Fault classes classified:** 8
**UI tabs:** 5
