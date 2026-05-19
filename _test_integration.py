"""Full integration smoke-test: stack + KB + agents."""
import sys, time
sys.path.insert(0, r'C:\Users\abhis\maritime-maintenance-demo')

from simulator import create_fleet
from pipeline import broker, DataHarmonizer, CEPEngine
from storage import TimeseriesStore, EventStore, WorkOrderStore
from storage.database import initialise_schema
from data.maintenance_history import MAINTENANCE_HISTORY
from agents import create_agents
from kb.retriever import _build_index, kb_retrieve_formatted
from kb.corpus import ALL_CHUNKS

# ── KB warmup ─────────────────────────────────────────────────────────
print(f"KB: {len(ALL_CHUNKS)} chunks — building TF-IDF index...")
t0 = time.monotonic()
_build_index()
print(f"KB index ready in {time.monotonic()-t0:.3f}s")

# Quick retrieval smoke-test
res = kb_retrieve_formatted("starting air compressor SOLAS minimum starts", asset_type="compressor")
import json
data = json.loads(res)
print(f"KB retrieval test: {data['total_found']} results for compressor SOLAS query")
assert data['total_found'] > 0, "KB retrieval returned no results!"
print(f"  Top result: {data['results'][0]['id']} (score {data['results'][0]['relevance_score']})")

# ── Stack boot ────────────────────────────────────────────────────────
initialise_schema()
wo_store = WorkOrderStore()
ev_store = EventStore()
ts_store = TimeseriesStore()
for wo in MAINTENANCE_HISTORY:
    wo_store.save_work_order(wo)

harmonizer = DataHarmonizer()
cep        = CEPEngine()
harmonizer.start()
cep.start()
ts_store.start()

fleet = create_fleet()
fleet["COMP-001"].inject_fault(0.25)

print("\nRunning 20 ticks...")
for _ in range(20):
    for sim in fleet.values():
        _, msgs = sim.tick()
        broker.publish_many(msgs)
    time.sleep(0.05)
time.sleep(1.5)

# ── Agents ────────────────────────────────────────────────────────────
ctx = {"ts_store": ts_store, "ev_store": ev_store, "wo_store": wo_store, "cep": cep}
agents = create_agents(ctx)

print("\n" + "="*60)
print("Agent tools check:")
for name, agent in agents.items():
    tools = [t["name"] for t in agent._get_tools()]
    has_kb = "kb_retrieve" in tools
    print(f"  {name:20s}: {len(tools)} tools  {'✓ kb_retrieve' if has_kb else '— no kb'}")

print("\nAll integration checks PASSED.")
