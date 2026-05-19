"""
MV-Callisto — Agentic AI Predictive Maintenance Demo
NordVast Maritime Fleet Management Technology | Powered by Claude
"""
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

# ── Page config (must be first Streamlit call) ─────────────────────────
st.set_page_config(
    page_title="MV-Callisto | AI Predictive Maintenance",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Imports ────────────────────────────────────────────────────────────
from data.inventory import ASSETS, all_assets
from data.maintenance_history import MAINTENANCE_HISTORY
from models.maintenance import WorkOrderStatus
from pipeline.uns_broker import broker
from pipeline.harmonizer import DataHarmonizer
from pipeline.cep_engine import CEPEngine
from pipeline.alarm_manager import alarm_manager
from pipeline.activity_log import (
    log_activity, get_log, clear_log, auto_watchkeeper_enabled as _auto_watchkeeper_enabled
)
from pipeline import incident_store
from simulator import create_fleet
from storage.database import initialise_schema
from storage.timeseries_store import TimeseriesStore
from storage.event_store import EventStore
from storage.workorder_store import WorkOrderStore
from storage.hf_store import hf_store, HF_RATE
from agents import create_agents
from kb.retriever import _build_index as kb_build_index
from kb.corpus import ALL_CHUNKS as KB_CHUNKS
from ml.pipeline import MLPipeline

# ── Colour helpers ─────────────────────────────────────────────────────
def health_color(score: float) -> str:
    if score >= 85:  return "#00C853"   # green
    if score >= 70:  return "#FFD600"   # yellow
    if score >= 55:  return "#FF6D00"   # orange
    return "#D50000"                    # red

def health_icon(score: float) -> str:
    if score >= 85:  return "🟢"
    if score >= 70:  return "🟡"
    if score >= 55:  return "🟠"
    return "🔴"

def severity_color(sev: str) -> str:
    return {"Info": "#29B6F6", "Warning": "#FFD600",
            "Alarm": "#FF6D00", "Critical": "#D50000"}.get(sev, "#888")


# ── Cascade helper functions ───────────────────────────────────────────

def _first_line(text: str | None, max_len: int = 140) -> str:
    """Extract first meaningful line from agent output for dossier display."""
    if not text:
        return "—"
    # Skip markdown headers and empty lines to find first content line
    for line in text.strip().split("\n"):
        line = line.strip().lstrip("#").strip()
        if len(line) > 10:
            return line[:max_len]
    return text.strip()[:max_len]

def _extract_compliance_status(text: str | None) -> str:
    """Parse compliance status from ISM agent text output."""
    if not text:
        return "Assessed"
    u = text.upper()
    for status in ("SOLAS VIOLATION", "MAJOR NC", "MAJOR NON-CONFORMITY",
                   "MINOR NC", "MINOR NON-CONFORMITY", "COMPLIANT"):
        if status in u:
            return status.replace("NON-CONFORMITY", "NC").replace("NON-", "").title()
    return "Assessed"

def _latest_wo_id(wo_store, before_count: int) -> str | None:
    """Return the newest draft WO if one was added since before_count."""
    try:
        all_wos = wo_store.get_all_work_orders(limit=10)
        if len(all_wos) > before_count:
            return all_wos[0].work_order_id
        pending = wo_store.get_pending_approval()
        if pending:
            return pending[-1].work_order_id
    except Exception:
        pass
    return None


# ── Fleet generation counter ───────────────────────────────────────────
# Incremented on every Reset Fleet. Each cascade thread captures the
# generation at dispatch time and checks it before every log write.
# If the counter has advanced (fleet was reset), the stale thread
# discards its output silently — no Activity Feed pollution after reset.
_fleet_generation = [0]   # mutable list so background threads see updates


def _agent_run_with_retry(agent, trigger: dict, max_retries: int = 3):
    """
    Run an agent with exponential backoff on 529 overloaded errors.
    Waits 5s → 10s → 20s between attempts before re-raising.
    """
    import time as _time
    last_exc = None
    for attempt in range(max_retries):
        try:
            return agent.run(trigger=trigger)
        except Exception as e:
            last_exc = e
            err_str = str(e)
            if "529" in err_str or "overloaded" in err_str.lower():
                if attempt < max_retries - 1:
                    wait = 5 * (2 ** attempt)   # 5s, 10s, 20s
                    logger.warning(
                        f"[Cascade] 529 overloaded on attempt {attempt+1} — "
                        f"retrying in {wait}s"
                    )
                    _time.sleep(wait)
                    continue
            raise
    raise last_exc


def _run_cascade(trigger: dict, agents: dict, wo_store, gen: int = 0, ml_pipeline=None):
    """
    Full agent chain for one alarm trigger. Runs in a background thread.
    Tier 2: Watchkeeper → Diagnostics → Planner
    Tier 3: Watchkeeper → Diagnostics → Planner + ISM Compliance + Fleet Intel
    """
    asset_id        = trigger.get("asset_id", "fleet")
    metric          = trigger.get("metric", "")
    tier            = trigger.get("tier", 2)
    compliance_code = trigger.get("compliance_code") or ""
    tier_tag        = f"T{tier}" + (" SOLAS" if tier >= 3 else "")

    # Helper: returns True if fleet was reset since this cascade was spawned
    def _stale() -> bool:
        return _fleet_generation[0] != gen

    # Create incident record — bail immediately if already reset
    if _stale():
        return
    inc = incident_store.create_incident(trigger)
    inc_id = inc.incident_id

    log_activity("🚨", "System", asset_id,
                 f"{inc_id} opened — {tier_tag} | {metric} alarm")

    # ── Step 1: Watchkeeper ──────────────────────────────────────────────
    if _stale(): return
    try:
        incident_store.start_step(inc_id, "watchkeeper")
        log_activity("🔭", "Watchkeeper", asset_id,
                     f"{inc_id} — confirming breach & cross-correlating sensors")
        wk_result  = _agent_run_with_retry(agents["watchkeeper"], trigger)
        if _stale(): return
        wk_summary = _first_line(wk_result.full_reasoning)
        incident_store.complete_watchkeeper(inc_id, wk_summary, len(wk_result.actions_taken),
                                            full_output=wk_result.full_reasoning)
        log_activity("✅", "Watchkeeper", asset_id,
                     f"{inc_id} — {len(wk_result.actions_taken)} calls · {wk_summary[:70]}")
    except Exception as e:
        if _stale(): return
        incident_store.complete_watchkeeper(inc_id, f"Error: {e}", 0)
        log_activity("❌", "Watchkeeper", asset_id, f"{inc_id} — error: {e}")
        return

    # ── Step 1.5: ML Analysis (runs after watchkeeper, before diagnostics) ──
    if _stale(): return
    ml_result  = None
    ml_summary = "ML analysis not available"
    try:
        incident_store.start_step(inc_id, "ml_analysis")
        log_activity("🧠", "ML Pipeline", asset_id,
                     f"{inc_id} — HF feature extraction + anomaly detection")

        # Get asset type from inventory
        from data.inventory import ASSETS as _ASSETS
        _asset = _ASSETS.get(asset_id)
        _asset_type = _asset.asset_type.value if _asset else "Unknown"

        # Get CEP health + RUL for conservative blending
        _derived = cep.latest_derived.get(asset_id)
        _cep_health = _derived.overall_health_score if _derived else None
        _cep_rul    = _derived.rul_days if _derived else None

        _ml_pipeline = ml_pipeline
        if _ml_pipeline:
            ml_result = _ml_pipeline.analyze(
                asset_id=asset_id,
                asset_type=_asset_type,
                duration_s=120,
                cep_health=_cep_health,
                cep_rul=_cep_rul,
            )
            incident_store.complete_ml_analysis(inc_id, ml_result)
            ml_summary = (
                f"{ml_result.fault_class.replace('_',' ')} p={ml_result.fault_probability:.2f} "
                f"· anomaly={ml_result.anomaly_score:.2f} · RUL={ml_result.rul_days:.1f}d"
            )
            log_activity("✅", "ML Pipeline", asset_id,
                         f"{inc_id} — {ml_summary}")
        else:
            incident_store.complete_ml_analysis(inc_id, None)
    except Exception as e:
        if _stale(): return
        log_activity("⚠️", "ML Pipeline", asset_id, f"{inc_id} — ML analysis error: {e}")
        try:
            incident_store.complete_ml_analysis(inc_id, None)
        except Exception:
            pass

    # ── Step 2: Deep Diagnostics ─────────────────────────────────────────
    if _stale(): return
    try:
        incident_store.start_step(inc_id, "diagnostics")
        log_activity("🔬", "Diagnostics", asset_id,
                     f"{inc_id} — root cause analysis started")
        # Enrich diagnostics trigger with ML results
        diag_trigger = {
            "asset_id":     asset_id,
            "reason":       trigger.get("reason", metric),
            "incident_id":  inc_id,
            "ml_fault_class": ml_result.fault_class if ml_result else None,
            "ml_narrative": ml_result.narrative[:500] if ml_result else None,
        }
        diag_result  = _agent_run_with_retry(agents["diagnostics"], diag_trigger)
        if _stale(): return
        diag_summary = _first_line(diag_result.full_reasoning)
        incident_store.complete_diagnostics(inc_id, diag_summary, len(diag_result.actions_taken),
                                            full_output=diag_result.full_reasoning)
        log_activity("✅", "Diagnostics", asset_id,
                     f"{inc_id} — {len(diag_result.actions_taken)} calls · {diag_summary[:70]}")
    except Exception as e:
        if _stale(): return
        incident_store.complete_diagnostics(inc_id, f"Error: {e}", 0)
        log_activity("❌", "Diagnostics", asset_id, f"{inc_id} — error: {e}")
        return

    # ── Step 3: Maintenance Planner ──────────────────────────────────────
    if _stale(): return
    try:
        incident_store.start_step(inc_id, "planner")
        log_activity("📋", "Planner", asset_id,
                     f"{inc_id} — creating work order from diagnostic findings")
        wo_count_before = len(wo_store.get_all_work_orders(limit=50))
        plan_trigger = {"asset_id": asset_id,
                        "diagnostic_summary": diag_summary,
                        "incident_id": inc_id}
        plan_result  = _agent_run_with_retry(agents["planner"], plan_trigger)
        if _stale(): return
        plan_summary = _first_line(plan_result.full_reasoning)
        wo_id        = _latest_wo_id(wo_store, wo_count_before)
        incident_store.complete_planner(inc_id, plan_summary, wo_id, len(plan_result.actions_taken),
                                        full_output=plan_result.full_reasoning)
        log_activity("✅", "Planner", asset_id,
                     f"{inc_id} — WO {wo_id or 'created'} · {plan_summary[:60]}")
    except Exception as e:
        if _stale(): return
        incident_store.complete_planner(inc_id, f"Error: {e}", None, 0)
        log_activity("❌", "Planner", asset_id, f"{inc_id} — error: {e}")

    # ── Step 4 + 5: ISM Compliance + Fleet Intel (Tier 3 only) ──────────
    if tier >= 3:
        if _stale(): return
        try:
            incident_store.start_step(inc_id, "compliance")
            log_activity("⚖️", "ISM Compliance", asset_id,
                         f"{inc_id} — {compliance_code} compliance check started")
            comp_trigger = {
                "asset_id": asset_id,
                "context":  f"{compliance_code} critical alarm: {metric} = "
                            f"{trigger.get('value', 0):.2f} {trigger.get('unit', '')}",
                "incident_id": inc_id,
            }
            comp_result  = _agent_run_with_retry(agents["compliance"], comp_trigger)
            if _stale(): return
            comp_summary = _first_line(comp_result.full_reasoning)
            comp_status  = _extract_compliance_status(comp_result.full_reasoning)
            incident_store.complete_compliance(inc_id, comp_summary, comp_status,
                                               len(comp_result.actions_taken),
                                               full_output=comp_result.full_reasoning)
            log_activity("✅", "ISM Compliance", asset_id,
                         f"{inc_id} — {comp_status} · {comp_summary[:60]}")
        except Exception as e:
            if _stale(): return
            incident_store.complete_compliance(inc_id, f"Error: {e}", "Unknown", 0)
            log_activity("❌", "ISM Compliance", asset_id, f"{inc_id} — error: {e}")

        if _stale(): return
        try:
            incident_store.start_step(inc_id, "fleet_intel")
            log_activity("🌐", "Fleet Intel", "fleet",
                         f"{inc_id} — fleet advisory update started")
            fi_trigger = {"asset_id": asset_id, "incident_id": inc_id}
            fi_result  = _agent_run_with_retry(agents["fleet_intel"], fi_trigger)
            if _stale(): return
            fi_summary = _first_line(fi_result.full_reasoning)
            incident_store.complete_fleet_intel(inc_id, fi_summary, len(fi_result.actions_taken),
                                                full_output=fi_result.full_reasoning)
            log_activity("✅", "Fleet Intel", "fleet",
                         f"{inc_id} — advisory issued · {fi_summary[:60]}")
        except Exception as e:
            if _stale(): return
            incident_store.complete_fleet_intel(inc_id, f"Error: {e}", 0)
            log_activity("❌", "Fleet Intel", "fleet", f"{inc_id} — error: {e}")


# ── Stack initialisation (runs once per session) ───────────────────────
def _init_stack():
    initialise_schema()

    wo_store = WorkOrderStore()
    for wo in MAINTENANCE_HISTORY:
        try:
            wo_store.save_work_order(wo)
        except Exception:
            pass

    harmonizer = DataHarmonizer()
    cep        = CEPEngine()
    ts_store   = TimeseriesStore()
    ev_store   = EventStore()

    # Clear stale sensor and event data from any previous session so the demo
    # always starts from a clean slate — no stale alarms or sawtooth charts.
    ts_store.clear_all()
    ev_store.clear_all()

    harmonizer.start()
    cep.start()
    ts_store.start()

    # Pre-warm KB index so first agent call is instant
    kb_build_index()

    fleet = create_fleet()
    # All assets start at full health (1.0). Use the fault buttons in
    # Demo Controls to inject faults and trigger the agent chain.

    # ── ML Pipeline init ──────────────────────────────────────────────
    # HFStore singleton imported above; create MLPipeline with it
    ml_pipeline = MLPipeline(hf_store)

    ctx = {"ts_store": ts_store, "ev_store": ev_store,
           "wo_store": wo_store, "cep": cep, "ml_pipeline": ml_pipeline}
    agents = create_agents(ctx)

    # Asset type registry for ML baseline fitting
    _asset_type_map = {aid: a.asset_type.value for aid, a in ASSETS.items()}

    # Background simulator thread (1 Hz — RT)
    stop_ev = threading.Event()
    def _sim_loop():
        while not stop_ev.is_set():
            for sim in fleet.values():
                _, msgs = sim.tick()
                broker.publish_many(msgs)
            time.sleep(1.0)

    # ── HF simulator thread (10 Hz) ───────────────────────────────────
    _hf_baseline_seconds = [0]   # counter for baseline accumulation

    def _hf_sim_loop():
        while not stop_ev.is_set():
            for sim in fleet.values():
                try:
                    sample = sim.tick_hf()
                    hf_store.update(sample)
                except Exception:
                    pass

            # During first 60s accumulate features for baseline fitting
            _hf_baseline_seconds[0] += 1
            if _hf_baseline_seconds[0] % 50 == 0:   # every ~5s
                if not ml_pipeline.baselines_fitted:
                    for aid, atype in _asset_type_map.items():
                        df = hf_store.get_window(aid, duration_s=5)
                        if df is not None:
                            ml_pipeline.accumulate_baseline(aid, atype, df)

            if _hf_baseline_seconds[0] == 600:   # after 60s, fit all
                ml_pipeline.try_fit_baselines(_asset_type_map)

            time.sleep(1.0 / HF_RATE)   # 10 Hz

    t = threading.Thread(target=_sim_loop, daemon=True, name="sim_loop")
    t.start()

    t_hf = threading.Thread(target=_hf_sim_loop, daemon=True, name="hf_sim_loop")
    t_hf.start()

    # Background trigger dispatcher — picks up AlarmManager triggers and
    # spawns a cascade thread per incident (so the dispatcher stays responsive
    # and can accept the next trigger while a cascade is still running).
    def _watchkeeper_loop():
        while not stop_ev.is_set():
            # Drain suppressed queue silently — debounce is internal plumbing,
            # not something the operator needs to see in the Activity Feed.
            while not alarm_manager.suppressed_queue.empty():
                try:
                    alarm_manager.suppressed_queue.get_nowait()
                except Exception:
                    break

            try:
                trigger = alarm_manager.trigger_queue.get(timeout=2.0)
                if not _auto_watchkeeper_enabled.is_set():
                    asset_id = trigger.get("asset_id", "?")
                    log_activity("⏸️", "System", asset_id,
                                 f"Trigger suppressed — Auto-Watchkeeper is OFF")
                    continue

                # Spawn cascade in its own thread so this dispatcher loop
                # can immediately accept the next trigger.
                cascade_t = threading.Thread(
                    target=_run_cascade,
                    args=(trigger, agents, wo_store, _fleet_generation[0], ml_pipeline),
                    daemon=True,
                    name=f"cascade_{trigger.get('asset_id','?')}",
                )
                cascade_t.start()

            except Exception:
                pass   # queue timeout — keep looping

    wk_thread = threading.Thread(target=_watchkeeper_loop, daemon=True,
                                 name="watchkeeper_trigger")
    wk_thread.start()

    st.session_state.update({
        "initialized": True,
        "fleet": fleet,
        "harmonizer": harmonizer,
        "cep": cep,
        "ts_store": ts_store,
        "ev_store": ev_store,
        "wo_store": wo_store,
        "agents": agents,
        "ml_pipeline": ml_pipeline,
        "stop_ev": stop_ev,
        "agent_results": {},   # agent_name -> AgentResult
        "agent_running": None,
    })

if "initialized" not in st.session_state:
    with st.spinner("🚢 Initialising MV-Callisto engine room systems..."):
        _init_stack()
        time.sleep(3)   # let CEP compute first batch

# Shorthand references
fleet       = st.session_state.fleet
cep         = st.session_state.cep
ts_store    = st.session_state.ts_store
ev_store    = st.session_state.ev_store
wo_store    = st.session_state.wo_store
agents      = st.session_state.agents
ml_pipeline = st.session_state.ml_pipeline

# ── Sidebar ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚢 MV-Callisto")
    st.markdown("**NordVast Maritime Fleet Management Technology**")
    st.markdown("*Agentic AI Predictive Maintenance*")
    st.divider()

    # Auto-refresh
    auto_refresh = st.toggle("⟳ Auto-refresh (2s)", value=True)
    auto_watchkeeper = st.toggle("🔭 Auto-Watchkeeper", value=True,
                                  help="When ON, Watchkeeper calls Claude API automatically on Alarm. Turn OFF to avoid unintended API usage.")
    # Sync to thread-safe flag so the background watchkeeper loop can read it safely
    if auto_watchkeeper:
        _auto_watchkeeper_enabled.set()
    else:
        _auto_watchkeeper_enabled.clear()

    st.divider()
    st.markdown("### 🎮 Demo Controls")
    st.markdown("**Inject fault to trigger agents:**")
    # Severity tuned so one click crosses the Alarm threshold for each asset:
    # PUMP: eff<65% at h≤0.15 (load-independent) | COMP: vol_eff<55% at h≤0.20
    # TURBO: eff<50% at h≤0.45 | PURIF: bowl_dev>7% at h≤0.45 | AUXGEN: freq_dev>1.5Hz at h≤0.40
    _FAULT_SEVERITY = {
        "PUMP-001":   0.85,   # h→0.15 → pump_efficiency reliably <65% across all load conditions
        "COMP-001":   0.80,
        "TURBO-001":  0.55,   # h→0.45 → turbo_efficiency 45% < 50% Alarm
        "PURIF-001":  0.55,
        "AUXGEN-001": 0.60,
    }
    cols = st.columns(2)
    asset_ids = list(fleet.keys())
    for i, aid in enumerate(asset_ids):
        col = cols[i % 2]
        sev = _FAULT_SEVERITY.get(aid, 0.25)
        drop_pct = int(sev * 100)
        if col.button(f"💥 {aid}", help=f"Degrade {aid} health by ~{drop_pct}% → triggers Alarm"):
            fleet[aid].inject_fault(sev)
            st.toast(f"Fault injected on {aid} — Watchkeeper will fire shortly", icon="⚠️")

    if st.button("♻️ Reset Fleet", use_container_width=True):
        _fleet_generation[0] += 1   # invalidate all in-flight cascade threads
        for sim in fleet.values():
            sim.reset()
        alarm_manager.clear_all()
        cep.reset()
        ts_store.clear_all()
        ev_store.clear_all()
        wo_store.clear_draft_orders()
        incident_store.clear_all()
        hf_store.clear()
        st.session_state.agent_results.clear()
        clear_log()
        log_activity("♻️", "System", "fleet", "Fleet reset — all assets restored, HF buffers cleared")
        st.toast("Fleet reset to healthy state", icon="✅")
        st.rerun()

    st.divider()
    st.markdown("### 📡 UNS Broker")
    bstats = broker.stats
    st.metric("Messages Published", f"{bstats['total_messages']:,}")
    st.metric("Active Subscriptions", bstats["total_subscribers"])
    st.caption("NordVast/MV-Callisto/EngineRoom/{Type}/{ID}/{Category}/{Tag}")

    st.divider()
    st.markdown("### 📚 Knowledge Base")
    st.metric("KB Chunks", len(KB_CHUNKS))
    st.caption("TF-IDF semantic search · ISO/IACS/SOLAS/OEM · Offline")

# ── Header ─────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='color:#00A0DE;margin-bottom:0'>🚢 MV-Callisto — Engine Room AI</h1>"
    "<p style='color:#8899AA;margin-top:4px'>Agentic Predictive Maintenance | NordVast FMT | "
    f"Last updated: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</p>",
    unsafe_allow_html=True,
)

# ── Tabs ───────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🛡️ Fleet Overview",
    "📈 Live Telemetry",
    "🔍 On-Demand Analysis",
    "🔧 Work Orders",
    "🚨 Incidents",
])

# ══════════════════════════════════════════════════════════════════════
# TAB 1 — Fleet Overview
# ══════════════════════════════════════════════════════════════════════
with tab1:
    derived_all = {aid: cep.latest_derived.get(aid) for aid in ASSETS}

    # Fleet status banner
    scores = [m.overall_health_score for m in derived_all.values() if m]
    fleet_score = sum(scores) / len(scores) if scores else 100
    banner_col, kpi1, kpi2, kpi3 = st.columns([3, 1, 1, 1])
    with banner_col:
        fleet_status = ("🟢 GREEN — All Systems Normal" if fleet_score >= 80
                        else "🟡 AMBER — Monitoring Required" if fleet_score >= 65
                        else "🔴 RED — Immediate Attention Required")
        st.markdown(
            f"<div style='background:{health_color(fleet_score)}22;border-left:4px solid "
            f"{health_color(fleet_score)};padding:12px;border-radius:6px'>"
            f"<b style='font-size:1.1em'>Fleet Status: {fleet_status}</b></div>",
            unsafe_allow_html=True,
        )
    kpi1.metric("Fleet Health", f"{fleet_score:.0f}/100")
    active_alerts = len(alarm_manager.get_active_alarms())
    kpi2.metric("Active Alarms", active_alerts, delta=None)
    pending_wo = len(wo_store.get_pending_approval())
    kpi3.metric("Pending WOs", pending_wo, delta=None)

    st.divider()
    st.markdown("### Asset Health Cards")

    # 5 asset cards
    cols = st.columns(5)
    for i, (asset_id, asset) in enumerate(ASSETS.items()):
        m = derived_all.get(asset_id)
        sim = fleet[asset_id]
        health = m.overall_health_score if m else 100.0
        rul    = m.rul_days if m else 60.0
        vib    = m.vibration_rms_mms if m else 0.0
        anomaly = m.anomaly_score if m else 0.0
        icon   = health_icon(health)
        col    = cols[i]

        with col:
            st.markdown(
                f"<div style='border:1px solid {health_color(health)};border-radius:8px;"
                f"padding:4px 12px 12px 12px;background:{health_color(health)}11'>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='padding:8px 0 4px 0'>"
                f"<span style='font-size:1.1em;font-weight:700'>{icon} {asset_id}</span><br>"
                f"<span style='color:#8899AA;font-size:0.8em'>{asset.display_name}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.metric("Health", f"{health:.0f}%",
                      delta=f"{health-100:.0f}%" if health < 100 else None)
            col_rul, col_vib = st.columns(2)
            col_rul.metric("RUL", f"{rul:.0f}d" if rul else "—")
            col_vib.metric("Vib", f"{vib:.2f}")
            if anomaly > 0.3:
                st.warning(f"Anomaly {anomaly:.2f}", icon="⚠️")
            elif anomaly > 0.15:
                st.info(f"Anomaly {anomaly:.2f}", icon="ℹ️")

            # HF buffer status + last ML result
            hf_status = hf_store.get_buffer_status().get(asset_id, {})
            hf_samples = hf_status.get("total_samples", 0)
            if hf_samples > 0:
                buffered_s = min(hf_samples / HF_RATE, 600)
                st.markdown(
                    f"<small style='color:#9C27B0'>🟣 HF: {buffered_s:.0f}s buffered</small>",
                    unsafe_allow_html=True,
                )
            ml_res = ml_pipeline.get_latest(asset_id)
            if ml_res and not ml_res.error:
                ml_color = "#D50000" if ml_res.anomaly_detected else "#00C853"
                st.markdown(
                    f"<small style='color:{ml_color}'>🧠 {ml_res.fault_class.replace('_',' ')}"
                    f" p={ml_res.fault_probability:.2f}</small>",
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

    # Fleet comparison bar chart
    st.divider()
    st.markdown("### Fleet Health Comparison")
    chart_data = []
    for asset_id, m in derived_all.items():
        if m:
            chart_data.append({
                "Asset": asset_id,
                "Health Score": m.overall_health_score,
                "RUL (days)": m.rul_days or 0,
                "Vibration (mm/s)": m.vibration_rms_mms or 0,
            })

    if chart_data:
        df_fleet = pd.DataFrame(chart_data)
        colors = [health_color(r["Health Score"]) for r in chart_data]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_fleet["Asset"], y=df_fleet["Health Score"],
            marker_color=colors, name="Health Score",
            text=df_fleet["Health Score"].round(1),
            textposition="outside",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#E8F0FE", height=280,
            yaxis=dict(range=[0, 110], gridcolor="#1E3A5F"),
            xaxis=dict(gridcolor="#1E3A5F"),
            showlegend=False, margin=dict(t=20, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Active threshold alarms (CEP-triggered, ISA-18.2 lifecycle) ──────────
    st.markdown("### 🔔 Active Alarms")
    active_alarms = alarm_manager.get_active_alarms()
    if active_alarms:
        for alm in active_alarms:
            alm_color = "#D50000" if alm.level == "Alarm" else "#FF6D00" if alm.level == "Warning" else "#FFD600"
            ack_label = "✓ Seen" if alm.acknowledged else "⚠️ Unacknowledged"
            col_alm, col_ack = st.columns([5, 1])
            with col_alm:
                st.markdown(
                    f"<div style='border-left:4px solid {alm_color};padding:8px 12px;"
                    f"margin:4px 0;background:{alm_color}18;border-radius:0 6px 6px 0'>"
                    f"<b style='color:{alm_color}'>{alm.level.upper()}</b> &nbsp;"
                    f"<b>{alm.asset_id}</b> — {alm.metric.replace('_',' ')}: "
                    f"<b>{alm.last_value:.2f} {alm.unit}</b> "
                    f"(limit {alm.threshold} {alm.unit})<br>"
                    f"<small style='color:#8899AA'>{alm.source[:80]} · "
                    f"Active {alm.age_minutes:.0f} min · {ack_label}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_ack:
                if not alm.acknowledged:
                    if st.button("Ack", key=f"ack_{alm.asset_id}_{alm.metric}",
                                 help="Acknowledge — alarm stays active until condition resolves"):
                        alarm_manager.acknowledge(alm.asset_id, alm.metric)
                        st.rerun()
    else:
        st.success("No active threshold alarms — all parameters within limits", icon="✅")

    # ── Live Agent Activity Feed ──────────────────────────────────────────────
    # Agent-colour map for the feed — each agent gets a distinct colour
    _AGENT_COLORS = {
        "Watchkeeper":   "#00A0DE",
        "ML Pipeline":   "#9C27B0",
        "Diagnostics":   "#00C853",
        "Planner":       "#FFD600",
        "ISM Compliance":"#FF6D00",
        "Fleet Intel":   "#B39DDB",
        "System":        "#607D8B",
    }
    active_incidents = incident_store.get_active()
    if active_incidents:
        st.markdown(
            f"<div style='background:#D50000{22:02X};border-left:4px solid #D50000;"
            f"padding:6px 14px;border-radius:0 6px 6px 0;margin-bottom:8px'>"
            f"🚨 <b>{len(active_incidents)} active incident(s)</b> — "
            f"see <b>Incidents</b> tab for full dossier &amp; agent chain status"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("### ⚡ Live Agent Activity")
    st.caption("Agent chain handoffs — each step shows which agent acted, on which asset, and what was found.")
    recent_activity = get_log()
    if recent_activity:
        feed_html = ""
        for entry in recent_activity:
            agent_name = entry.get("agent", "")
            agent_color = _AGENT_COLORS.get(agent_name, "#8899AA")
            icon = entry["icon"]
            feed_html += (
                f"<div style='display:flex;align-items:baseline;gap:8px;"
                f"padding:5px 10px;border-bottom:1px solid #1E3A5F;font-size:0.82em'>"
                f"<span style='color:#4A6F8F;min-width:68px;font-family:monospace'>{entry['ts']}</span>"
                f"<span style='min-width:18px'>{icon}</span>"
                f"<span style='color:{agent_color};min-width:110px;font-weight:600'>{agent_name}</span>"
                f"<span style='color:#00A0DE;min-width:75px'>{entry['asset']}</span>"
                f"<span style='color:#B0C4D8'>{entry['message']}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div style='background:#0A1628;border:1px solid #1E3A5F;border-radius:8px;"
            f"max-height:240px;overflow-y:auto;font-family:monospace'>{feed_html}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='background:#0A1628;border:1px solid #1E3A5F;border-radius:8px;"
            "padding:12px 16px;color:#4A6F8F;font-size:0.85em;font-family:monospace'>"
            "⏳ Waiting for agent activity... Inject a fault to see the full incident chain fire."
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Agent-raised alerts (diagnostic findings) ─────────────────────────────
    st.markdown("### 📋 Agent Alerts")
    events = ev_store.get_active_events(limit=8)
    if events:
        for ev in events:
            color = severity_color(ev["severity"])
            st.markdown(
                f"<div style='border-left:3px solid {color};padding:6px 12px;"
                f"margin:4px 0;background:{color}11;border-radius:0 4px 4px 0'>"
                f"<b>{ev['asset_id']}</b> · <span style='color:{color}'>{ev['severity']}</span>"
                f" · {ev['title']}<br>"
                f"<small style='color:#8899AA'>{ev['ts'][:19]} UTC"
                f"{' | ' + ev['agent_name'] if ev['agent_name'] else ''}</small></div>",
                unsafe_allow_html=True,
            )
    else:
        st.info("No agent alerts raised yet")

# ══════════════════════════════════════════════════════════════════════
# TAB 2 — Live Telemetry
# ══════════════════════════════════════════════════════════════════════
with tab2:
    sel_col1, sel_col2 = st.columns([1, 2])
    with sel_col1:
        sel_asset = st.selectbox(
            "Asset", list(ASSETS.keys()),
            format_func=lambda aid: f"{aid} — {ASSETS[aid].display_name}",
        )
    asset_obj = ASSETS[sel_asset]

    # Tag options per asset type
    TAG_OPTIONS = {
        "Pump":         ["bearing_temp_c", "vibration_x_mms", "vibration_y_mms",
                         "discharge_pressure_bar", "flow_rate_m3h", "motor_current_a"],
        "Compressor":   ["vibration_mms", "outlet_pressure_bar", "outlet_temp_c",
                         "motor_current_a", "oil_pressure_bar"],
        "Turbocharger": ["vibration_mms", "speed_rpm", "boost_pressure_bar",
                         "exhaust_temp_in_c", "exhaust_temp_out_c", "lube_oil_pressure_bar"],
        "Purifier":     ["vibration_mms", "bowl_speed_rpm", "motor_current_a",
                         "back_pressure_bar", "feed_temp_c"],
        "Generator":    ["frequency_hz", "load_kw", "exhaust_temp_c",
                         "coolant_temp_c", "lube_oil_pressure_bar", "fuel_consumption_lh"],
    }
    tags = TAG_OPTIONS.get(asset_obj.asset_type.value, ["vibration_mms"])
    with sel_col2:
        sel_tag = st.selectbox("Sensor Tag", tags)

    # Time series chart
    history = ts_store.get_tag_history(sel_asset, sel_tag, limit=120)
    if history:
        df = pd.DataFrame(history)
        df["ts"] = pd.to_datetime(df["ts"], format="ISO8601", utc=True)
        fig = px.line(
            df, x="ts", y="value",
            title=f"{sel_tag} — {sel_asset} ({asset_obj.display_name})",
            labels={"value": sel_tag, "ts": "Time (UTC)"},
            color_discrete_sequence=["#00A0DE"],
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#E8F0FE", height=340,
            yaxis=dict(gridcolor="#1E3A5F"),
            xaxis=dict(gridcolor="#1E3A5F"),
            margin=dict(t=40, b=20),
        )
        # Add threshold lines for known alarm limits
        thresholds = {
            "bearing_temp_c": (70, "Warning"), "vibration_x_mms": (4.5, "Warning"),
            "vibration_mms": (4.5, "Warning"), "vibration_y_mms": (4.5, "Warning"),
            "frequency_hz":  (60.5, "Warning"),
        }
        if sel_tag in thresholds:
            val, label = thresholds[sel_tag]
            fig.add_hline(y=val, line_dash="dash", line_color="#FFD600",
                          annotation_text=f"{label}: {val}", annotation_position="top right")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Collecting data... refresh in a moment.")

    # Derived health trend
    st.markdown("#### Health & RUL Trend")
    derived_hist = ts_store.get_derived_history(sel_asset, limit=60)
    if derived_hist:
        df_d = pd.DataFrame(derived_hist)
        df_d["ts"] = pd.to_datetime(df_d["ts"], format="ISO8601", utc=True)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df_d["ts"], y=df_d["health_score"],
            name="Health Score", line=dict(color="#00C853", width=2),
        ))
        fig2.add_trace(go.Scatter(
            x=df_d["ts"], y=df_d["rul_days"],
            name="RUL (days)", line=dict(color="#00A0DE", width=2),
            yaxis="y2",
        ))
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#E8F0FE", height=260,
            yaxis=dict(title="Health Score (0–100)", gridcolor="#1E3A5F", range=[0, 110]),
            yaxis2=dict(title="RUL (days)", overlaying="y", side="right", gridcolor="#1E3A5F"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=30, b=20),
        )
        st.plotly_chart(fig2, width="stretch")

    # Current readings table
    st.markdown("#### Current Readings")
    readings = ts_store.get_latest_readings(sel_asset)
    if readings:
        df_r = pd.DataFrame([{"Tag": k, "Value": round(v, 3)} for k, v in readings.items()])
        st.dataframe(df_r, use_container_width=True, hide_index=True, height=220)

    # UNS topic explorer
    with st.expander("🔍 UNS Topic Structure"):
        asset_type = asset_obj.asset_type.value
        st.code(
            f"NordVast/MV-Callisto/EngineRoom/{asset_type}/{sel_asset}/Raw/{sel_tag}\n"
            f"NordVast/MV-Callisto/EngineRoom/{asset_type}/{sel_asset}/Derived/health_snapshot\n"
            f"NordVast/MV-Callisto/EngineRoom/{asset_type}/{sel_asset}/Events/agent_alert",
            language="text",
        )
        st.caption(
            "ISA-95 Unified Namespace hierarchy. "
            "Raw → Harmonizer → CEP → Derived. "
            "All agents subscribe to the same broker."
        )

# ══════════════════════════════════════════════════════════════════════
# TAB 3 — On-Demand Analysis
# ══════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 🔍 On-Demand Analysis — Chief Engineer Investigation Tool")
    st.caption(
        "Proactive, human-initiated analysis — run any agent on demand, at any time, without waiting for an alarm. "
        "Use this for pre-departure checks, post-repair verification, borderline asset investigation, and voyage planning."
    )
    st.markdown(
        "<div style='background:#00358018;border-left:3px solid #003580;"
        "padding:8px 14px;border-radius:0 6px 6px 0;margin:0 0 16px 0;font-size:0.85em;color:#B0C8E8'>"
        "⚡ <b>Reactive vs. Proactive:</b> The <b>Incidents</b> tab shows what the AI found automatically when alarms fired. "
        "This tab is for what <b>you</b> choose to investigate — on your schedule, on any asset, for any reason."
        "</div>",
        unsafe_allow_html=True,
    )

    # Agent selector cards
    # Tuple: (icon, title, role, model, est_time, what_it_does, business_impact)
    AGENT_META = {
        "watchkeeper": (
            "🔭", "Realtime Watchkeeper", "2nd Engineer on Watch",
            "claude-haiku-4-5", "~5–10s",
            "Scans all 5 assets for threshold breaches",
            "Catches bearing/vibration failures 6–12h before physical alarm. "
            "Each missed failure = ~$85K unplanned port detention + crew overtime.",
        ),
        "diagnostics": (
            "🔬", "Deep Diagnostics", "Chief Engineer Assessment",
            "claude-sonnet-4-6", "~15–20s",
            "Root cause analysis + RUL estimation per asset",
            "Replaces 2–3h manual chief engineer investigation with a 20s structured report. "
            "Identifies degradation pattern (wear ring vs. bearing vs. seal) before physical failure.",
        ),
        "planner": (
            "📋", "Maintenance Planner", "Technical Superintendent",
            "claude-sonnet-4-6", "~15–25s",
            "Creates work orders aligned to port calls & spare parts",
            "Eliminates reactive scheduling. Aligns maintenance windows to port calls — "
            "avg $12K saved per avoided emergency repair vs. planned maintenance.",
        ),
        "compliance": (
            "⚖️", "ISM Compliance", "DPA / ISM Manager",
            "claude-sonnet-4-6", "~10–15s",
            "Checks ISM Code, SOLAS & class survey requirements",
            "Flags Class overdue items and SOLAS deficiencies before port state control inspection. "
            "Avg PSC detention costs NordVast $35K/day + reputational risk.",
        ),
        "fleet_intel": (
            "🌐", "Fleet Intelligence", "Remote Operations Centre",
            "claude-opus-4-7", "~20–35s",
            "Executive fleet report with MTBF & cost outlook",
            "Replaces the 4-hour weekly Chief Engineer report with a 30-second AI summary. "
            "Surfaces cross-asset MTBF trends invisible to per-vessel engineers.",
        ),
    }

    sel_agent = st.radio(
        "Choose which AI agent to interrogate:",
        list(AGENT_META.keys()),
        format_func=lambda k: f"{AGENT_META[k][0]} {AGENT_META[k][1]}",
        horizontal=True,
    )

    icon, title, role, model, est_time, description, business_impact = AGENT_META[sel_agent]

    # Agent info row
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**Role:** {role}")
    c2.markdown(f"**Model:** `{model}`")
    c3.markdown(f"**Est. time:** {est_time}")
    c4.markdown(f"**{description}**")

    # Business impact highlight
    st.markdown(
        f"<div style='background:#00A0DE18;border-left:3px solid #00A0DE;"
        f"padding:8px 14px;border-radius:0 6px 6px 0;margin:6px 0 12px 0;"
        f"font-size:0.88em;color:#B0D4EA'>"
        f"💡 <b>Business impact:</b> {business_impact}</div>",
        unsafe_allow_html=True,
    )

    # Optional asset focus
    trigger_asset = None
    if sel_agent in ("diagnostics", "planner", "compliance"):
        trigger_asset = st.selectbox(
            "Focus on a specific asset (or leave fleet-wide):",
            ["— Fleet-wide —"] + list(ASSETS.keys()),
        )
        trigger_asset = None if trigger_asset.startswith("—") else trigger_asset

    # Use-case hint
    USE_CASE_HINTS = {
        "watchkeeper":  "💡 Use this before departure — confirm no undetected threshold breaches across the fleet.",
        "diagnostics":  "💡 Use this when an asset's health score is trending down but hasn't triggered an alarm yet.",
        "planner":      "💡 Use this after a repair to generate a revised maintenance plan, or before a port call to align WO scheduling.",
        "compliance":   "💡 Use this ahead of a port state control inspection to catch any SOLAS/ISM gaps.",
        "fleet_intel":  "💡 Use this for voyage planning or superintendency review — 30-second AI fleet summary instead of a 4-hour report.",
    }
    st.caption(USE_CASE_HINTS.get(sel_agent, ""))

    # Run button
    if st.button(f"{icon} Run {title}", type="primary"):
        trigger = {"asset_id": trigger_asset} if trigger_asset else None
        focus = trigger_asset or "fleet"
        log_activity(icon, sel_agent, focus, f"On-Demand: {title} initiated by Chief Engineer")
        with st.spinner(f"⚙️ {title} reasoning... ({est_time})"):
            result = agents[sel_agent].run(trigger=trigger)
        st.session_state.agent_results[sel_agent] = result
        log_activity("✅", sel_agent, focus,
                     f"On-Demand: {title} done — {len(result.actions_taken)} tool calls, {result.duration_s:.1f}s")
        st.toast(f"{title} completed in {result.duration_s:.1f}s", icon="✅")

    # Agent output
    result = st.session_state.agent_results.get(sel_agent)
    if result:
        st.divider()
        meta_c1, meta_c2, meta_c3 = st.columns(3)
        meta_c1.metric("Duration", f"{result.duration_s:.1f}s")
        meta_c2.metric("Tool Calls", len(result.actions_taken))
        meta_c3.metric("Timestamp", result.timestamp.strftime("%H:%M UTC"))

        # Tool call trace — expanded by default so the "AI thinking" is immediately visible
        with st.expander(f"🛠️ Tool Call Trace ({len(result.actions_taken)} calls)", expanded=True):
            st.caption("Every tool call Claude made to reason about this fleet — live data, not cached responses.")
            for i, action in enumerate(result.actions_taken, 1):
                tool_color = {"get_asset_telemetry": "#00C853", "get_alarm_history": "#FF6D00",
                              "get_maintenance_history": "#00A0DE", "create_work_order": "#FFD600",
                              "get_fleet_summary": "#29B6F6"}.get(action['tool'], "#8899AA")
                st.markdown(
                    f"<span style='background:{tool_color}22;border:1px solid {tool_color}44;"
                    f"padding:2px 8px;border-radius:4px;font-size:0.8em;color:{tool_color}'>"
                    f"call {i}</span> <code>{action['tool']}</code>",
                    unsafe_allow_html=True,
                )
                if action.get("input"):
                    st.json(action["input"], expanded=False)

        st.markdown("#### Analysis Output")
        if result.full_reasoning:
            with st.container(border=True):
                st.markdown(result.full_reasoning)
        else:
            st.warning("Agent completed tool calls but produced no final text response.")

        # Check for new WOs created during this run
        new_wos = wo_store.get_pending_approval()
        if new_wos:
            st.info(f"📋 {len(new_wos)} work order(s) created — see **Work Orders** tab for approval",
                    icon="ℹ️")
    else:
        st.info(
            "Select an agent above and click **Run** to start an on-demand investigation. "
            "The AI will call live tools and reason about your fleet in real time.",
            icon="🔍",
        )

# ══════════════════════════════════════════════════════════════════════
# TAB 4 — Work Orders (HITL)
# ══════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 🔧 Maintenance Work Orders")
    st.caption(
        "AI-generated work orders require **Chief Engineer approval** before scheduling. "
        "This is the human-in-the-loop gate."
    )

    # Summary metrics
    summary = wo_store.get_summary()
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Draft (Pending)", summary.get("Draft", 0))
    mc2.metric("Approved",        summary.get("Approved", 0))
    mc3.metric("Completed",       summary.get("Completed", 0))
    mc4.metric("Total",           sum(summary.values()))

    # ── Pending approval (HITL gate) ──────────────────────────────────
    pending = wo_store.get_pending_approval()
    if pending:
        st.divider()
        st.markdown(f"#### ⏳ Awaiting Chief Engineer Approval ({len(pending)})")
        for wo in pending:
            p_color = {1: "#D50000", 2: "#FF6D00", 3: "#FFD600",
                       4: "#00C853", 5: "#29B6F6"}.get(wo.priority, "#888")
            with st.container(border=True):
                h1, h2, h3 = st.columns([3, 1, 1])
                with h1:
                    st.markdown(
                        f"<span style='background:{p_color};color:#000;padding:2px 8px;"
                        f"border-radius:4px;font-size:0.75em'>P{wo.priority}</span> "
                        f"**{wo.work_order_id}** — {wo.title}",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"{wo.asset_id} | {wo.maintenance_type.value} | "
                               f"Est. {wo.estimated_duration_hours:.0f}h | "
                               f"{'Port required' if wo.requires_port else 'Can do at sea'}"
                               + (f" | Est. ${wo.estimated_cost_usd:,.0f}" if wo.estimated_cost_usd else ""))
                h2.markdown(f"**Window:**  \n{wo.recommended_window or '—'}")
                with h3:
                    if st.button("✅ Approve", key=f"approve_{wo.work_order_id}", type="primary"):
                        wo_store.approve_work_order(wo.work_order_id, "Chief Engineer")
                        st.toast(f"{wo.work_order_id} approved!", icon="✅")
                        st.rerun()
                    if st.button("❌ Reject", key=f"reject_{wo.work_order_id}"):
                        wo_store.update_status(wo.work_order_id, WorkOrderStatus.CANCELLED)
                        st.toast(f"{wo.work_order_id} cancelled", icon="🗑️")
                        st.rerun()

                with st.expander("📄 AI Rationale & Scope"):
                    st.markdown(f"**Description:** {wo.description}")
                    st.markdown(f"**AI Rationale:** {wo.ai_rationale}")
                    if wo.requires_class_surveyor:
                        st.warning("⚠️ Class surveyor required", icon="⚠️")
    else:
        st.success("No work orders pending approval", icon="✅")

    # ── All work orders table ─────────────────────────────────────────
    st.divider()
    st.markdown("#### All Work Orders")
    status_filter = st.multiselect(
        "Filter by status",
        ["Draft", "Approved", "Scheduled", "In Progress", "Completed", "Cancelled"],
        default=["Draft", "Approved", "Completed"],
    )

    all_wos = wo_store.get_all_work_orders(limit=50)
    filtered = [wo for wo in all_wos if wo.status.value in status_filter]
    if filtered:
        rows = []
        for wo in filtered:
            rows.append({
                "WO ID":     wo.work_order_id,
                "Asset":     wo.asset_id,
                "Priority":  f"P{wo.priority}",
                "Title":     wo.title[:55],
                "Type":      wo.maintenance_type.value,
                "Status":    wo.status.value,
                "Est. $":    f"${wo.estimated_cost_usd:,.0f}" if wo.estimated_cost_usd else "—",
                "Created":   wo.created_at.strftime("%Y-%m-%d") if wo.created_at else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No work orders match the selected filters.")

# ══════════════════════════════════════════════════════════════════════
# TAB 5 — Incidents Dossier
# ══════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("### 🚨 Incident Dossier — Agentic Chain Audit Trail")
    st.caption(
        "Every alarm-triggered incident is recorded here with full agent chain traceability. "
        "Each step shows which agent ran, when, how many tool calls it made, and what it found. "
        "Tier 3 (SOLAS/ISM) incidents cascade through all 5 agents automatically."
    )

    # ── Tier legend ───────────────────────────────────────────────────
    leg_c1, leg_c2, leg_c3 = st.columns(3)
    with leg_c1:
        st.markdown(
            "<span style='background:#D5000033;border:1px solid #D50000;padding:3px 10px;"
            "border-radius:4px;font-size:0.82em;color:#FF6B6B'>"
            "🔴 TIER 3 — SOLAS/ISM Critical → 5-agent chain</span>",
            unsafe_allow_html=True,
        )
    with leg_c2:
        st.markdown(
            "<span style='background:#FF6D0033;border:1px solid #FF6D00;padding:3px 10px;"
            "border-radius:4px;font-size:0.82em;color:#FFB74D'>"
            "🟠 TIER 2 — Investigate → 3-agent chain</span>",
            unsafe_allow_html=True,
        )
    with leg_c3:
        st.markdown(
            "<span style='background:#607D8B33;border:1px solid #607D8B;padding:3px 10px;"
            "border-radius:4px;font-size:0.82em;color:#B0BEC5'>"
            "⚪ TIER 1 — Monitor only (Warnings: no cascade)</span>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Filter ────────────────────────────────────────────────────────
    filter_col, _, count_col = st.columns([2, 3, 1])
    with filter_col:
        inc_filter = st.selectbox(
            "Filter by status",
            ["All", "Open", "Chain Complete", "Pending WO Approval", "Resolved"],
            key="inc_filter",
        )
    all_incidents = incident_store.get_all(limit=30)
    if inc_filter != "All":
        all_incidents = [i for i in all_incidents if i.status == inc_filter]

    with count_col:
        st.metric("Incidents", len(all_incidents))

    if not all_incidents:
        st.markdown(
            "<div style='background:#0A1628;border:1px solid #1E3A5F;border-radius:8px;"
            "padding:28px;text-align:center;color:#4A6F8F;font-size:0.92em'>"
            "⏳ No incidents yet — inject a fault to trigger the agent chain.<br>"
            "<small>Only Alarm-level breaches on critical parameters cascade to agents.</small>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        for inc in all_incidents:
            tier_border = "#D50000" if inc.tier >= 3 else "#FF6D00"
            tier_bg     = "#D5000018" if inc.tier >= 3 else "#FF6D0015"

            # ── Incident header card ──────────────────────────────────
            with st.container():
                st.markdown(
                    f"<div style='border:1px solid {tier_border};border-radius:8px;"
                    f"background:{tier_bg};padding:12px 18px;margin-bottom:4px'>",
                    unsafe_allow_html=True,
                )
                hdr_c1, hdr_c2, hdr_c3, hdr_c4 = st.columns([2, 2, 2, 1])
                with hdr_c1:
                    st.markdown(
                        f"<b style='font-size:1.05em;color:{tier_border}'>{inc.incident_id}</b><br>"
                        f"<span style='color:#8899AA;font-size:0.82em'>{inc.tier_label}</span>",
                        unsafe_allow_html=True,
                    )
                with hdr_c2:
                    st.markdown(
                        f"<b>{inc.asset_id}</b> · {inc.metric.replace('_',' ')}<br>"
                        f"<span style='color:#8899AA;font-size:0.82em'>"
                        f"{inc.trigger_level}: {inc.trigger_value:.2f} {inc.trigger_unit} "
                        f"(limit {inc.trigger_threshold:.2f})</span>",
                        unsafe_allow_html=True,
                    )
                with hdr_c3:
                    triggered_str = inc.triggered_at.strftime("%Y-%m-%d %H:%M UTC")
                    age_str = f"{inc.age_minutes:.0f} min ago"
                    status_color = {"Open": "#D50000", "Chain Complete": "#00C853",
                                    "Pending WO Approval": "#FFD600",
                                    "Resolved": "#607D8B"}.get(inc.status, "#8899AA")
                    st.markdown(
                        f"<span style='background:{status_color}33;border:1px solid {status_color};"
                        f"padding:2px 8px;border-radius:4px;font-size:0.78em;color:{status_color}'>"
                        f"{inc.status}</span><br>"
                        f"<span style='color:#8899AA;font-size:0.78em'>{triggered_str} · {age_str}</span>",
                        unsafe_allow_html=True,
                    )
                with hdr_c4:
                    done  = inc.steps_done
                    total = inc.steps_total_active
                    st.metric("Steps", f"{done}/{total}")
                    if inc.wo_id:
                        st.caption(f"WO: {inc.wo_id}")
                st.markdown("</div>", unsafe_allow_html=True)

            # ── Agent chain timeline ──────────────────────────────────
            with st.expander(
                f"🔍 Agent Chain — {inc.incident_id}  "
                f"({'✅ Complete' if inc.chain_complete else '⏳ In Progress'})",
                expanded=(inc.status == "Open" and not inc.chain_complete),
            ):
                # ── 🧠 ML Analysis Results panel ──────────────────────
                _ml = getattr(inc, "ml_result", None)
                if _ml and not getattr(_ml, "error", None):
                    ml = _ml
                    st.markdown(
                        "<div style='background:#9C27B015;border:1px solid #9C27B066;"
                        "border-radius:6px;padding:10px 14px;margin-bottom:10px'>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("**🧠 ML Analysis Results** *(High-Frequency 10 Hz pipeline)*")
                    mc1, mc2, mc3 = st.columns(3)
                    anom_delta = "🔴 ANOMALY" if ml.anomaly_detected else "🟢 normal"
                    mc1.metric("Anomaly Score", f"{ml.anomaly_score*100:.0f}%",
                               delta=anom_delta,
                               delta_color="inverse" if ml.anomaly_detected else "off")
                    mc2.metric("Fault Class",
                               ml.fault_class.replace("_", " ").title(),
                               delta=f"p={ml.fault_probability:.2f}")
                    mc3.metric("HF RUL", f"{ml.rul_days:.1f} days",
                               delta=ml.rul_confidence + " confidence")

                    mf1, mf2, mf3 = st.columns(3)
                    mf1.metric("Dominant Freq", f"{ml.dominant_frequency_hz:.0f} Hz")
                    mf2.metric("Kurtosis", f"{ml.kurtosis:.1f}",
                               delta="⚠ bearing defect" if ml.kurtosis > 4 else "normal",
                               delta_color="inverse" if ml.kurtosis > 4 else "off")
                    mf3.metric("Crest Factor", f"{ml.crest_factor:.1f}",
                               delta="⚠ impulsive" if ml.crest_factor > 6 else "normal",
                               delta_color="inverse" if ml.crest_factor > 6 else "off")

                    with st.expander("📊 ML Feature Detail & Narrative",
                                     key=f"ml_detail_{inc.incident_id}"):
                        st.markdown(ml.narrative)
                        if ml.fault_candidates:
                            st.markdown("**Top fault candidates:**")
                            for cand in ml.fault_candidates:
                                bar_width = int(cand["probability"] * 100)
                                st.markdown(
                                    f"`{cand['class'].replace('_',' '):<20}` "
                                    f"{'█' * max(1, bar_width//5)} {cand['probability']:.3f}",
                                )
                        if ml.feature_detail:
                            st.json(ml.feature_detail, expanded=False)
                    st.markdown("</div>", unsafe_allow_html=True)

                elif _ml and getattr(_ml, "error", None):
                    st.warning(f"🧠 ML Analysis: {_ml.error}", icon="⚠️")

                st.divider()

                # Quick metadata row
                meta_cols = st.columns(4)
                if inc.compliance_code:
                    meta_cols[0].markdown(
                        f"**Compliance:** `{inc.compliance_code}`"
                    )
                if inc.compliance_status:
                    cs_color = {"Compliant": "#00C853", "Minor Nc": "#FFD600",
                                "Major Nc": "#D50000", "Solas Violation": "#D50000"
                                }.get(inc.compliance_status, "#8899AA")
                    meta_cols[1].markdown(
                        f"<span style='color:{cs_color}'><b>ISM: {inc.compliance_status}</b></span>",
                        unsafe_allow_html=True,
                    )
                if inc.wo_id:
                    meta_cols[2].markdown(f"**Work Order:** `{inc.wo_id}`")
                if inc.fleet_advisory:
                    meta_cols[3].markdown("**Fleet advisory:** issued ✅")

                st.divider()

                # Step-by-step chain timeline
                _STATUS_COLOR = {
                    "done":    "#00C853",
                    "running": "#00A0DE",
                    "pending": "#607D8B",
                    "skipped": "#37474F",
                    "error":   "#D50000",
                }
                _STEP_ORDER = ["watchkeeper", "ml_analysis", "diagnostics", "planner",
                               "compliance", "fleet_intel"]

                for step_name in _STEP_ORDER:
                    step = inc.steps.get(step_name)
                    if not step:
                        continue
                    sc = _STATUS_COLOR.get(step.status, "#8899AA")
                    is_skipped = step.status == "skipped"

                    scol1, scol2, scol3, scol4 = st.columns([1, 2, 4, 1])
                    with scol1:
                        status_icon = {
                            "done": "✅", "running": "⚙️",
                            "pending": "⏳", "skipped": "➖",
                        }.get(step.status, "❓")
                        st.markdown(
                            f"<div style='text-align:center;padding:6px 0;"
                            f"opacity:{'0.35' if is_skipped else '1.0'}'>"
                            f"{step.icon} {status_icon}</div>",
                            unsafe_allow_html=True,
                        )
                    with scol2:
                        opacity = "0.35" if is_skipped else "1.0"
                        st.markdown(
                            f"<div style='opacity:{opacity}'>"
                            f"<b style='color:{sc}'>{step.label}</b><br>"
                            f"<span style='font-size:0.78em;color:#8899AA'>{step.time_str}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    with scol3:
                        if step.summary and not is_skipped:
                            st.markdown(
                                f"<div style='background:{sc}15;border-left:3px solid {sc};"
                                f"padding:5px 10px;border-radius:0 4px 4px 0;font-size:0.83em;"
                                f"color:#C8D8E8'>{step.summary[:160]}</div>",
                                unsafe_allow_html=True,
                            )
                        elif is_skipped:
                            st.markdown(
                                f"<div style='color:#37474F;font-size:0.80em;padding:5px 0'>"
                                f"<i>{step.summary or 'Not triggered for this tier'}</i></div>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"<div style='color:#4A6F8F;font-size:0.80em;padding:5px 0'>"
                                f"{'Running...' if step.status == 'running' else 'Waiting...'}</div>",
                                unsafe_allow_html=True,
                            )
                    with scol4:
                        if step.tool_calls > 0:
                            st.markdown(
                                f"<div style='text-align:center;font-size:0.78em;"
                                f"color:#8899AA'>{step.tool_calls}<br><small>calls</small></div>",
                                unsafe_allow_html=True,
                            )
                        if step.duration_s > 0:
                            st.markdown(
                                f"<div style='text-align:center;font-size:0.78em;"
                                f"color:#4A6F8F'>{step.duration_s:.1f}s</div>",
                                unsafe_allow_html=True,
                            )

                    # Full analysis expander — shown below the step row when output is available
                    if step.full_output and step.status == "done":
                        with st.expander(
                            f"📄 {step.label} — Full Analysis",
                            expanded=False,
                            key=f"full_{inc.incident_id}_{step_name}",
                        ):
                            st.markdown(step.full_output)

                # ── WO approval shortcut if pending ──────────────────
                if inc.wo_id:
                    st.divider()
                    wo_obj = wo_store.get_all_work_orders(limit=50)
                    matched = [w for w in wo_obj if w.work_order_id == inc.wo_id]
                    if matched:
                        wo = matched[0]
                        if wo.status.value == "Draft":
                            st.markdown(
                                f"<div style='background:#FFD60018;border:1px solid #FFD600;"
                                f"padding:8px 14px;border-radius:6px;margin-top:8px'>"
                                f"⏳ <b>Work Order {inc.wo_id} awaiting Chief Engineer approval</b><br>"
                                f"<small style='color:#8899AA'>{wo.title}</small></div>",
                                unsafe_allow_html=True,
                            )
                            ap_col, rj_col, _ = st.columns([1, 1, 4])
                            with ap_col:
                                if st.button("✅ Approve WO", key=f"inc_approve_{inc.incident_id}",
                                             type="primary"):
                                    wo_store.approve_work_order(inc.wo_id, "Chief Engineer")
                                    st.toast(f"{inc.wo_id} approved!", icon="✅")
                                    st.rerun()
                            with rj_col:
                                if st.button("❌ Reject WO", key=f"inc_reject_{inc.incident_id}"):
                                    wo_store.update_status(inc.wo_id, WorkOrderStatus.CANCELLED)
                                    st.toast(f"{inc.wo_id} cancelled", icon="🗑️")
                                    st.rerun()
                        else:
                            st.success(
                                f"Work Order {inc.wo_id} — {wo.status.value}",
                                icon="✅" if wo.status.value == "Approved" else "ℹ️",
                            )

                # ── Fleet advisory snippet ────────────────────────────
                if inc.fleet_advisory:
                    st.divider()
                    st.markdown(
                        f"<div style='background:#B39DDB15;border-left:3px solid #B39DDB;"
                        f"padding:8px 12px;border-radius:0 6px 6px 0;font-size:0.83em;"
                        f"color:#C8D8E8'><b>🌐 Fleet Advisory:</b><br>{inc.fleet_advisory[:200]}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            st.markdown("---")


# ── Auto-refresh ───────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(2)
    st.rerun()
