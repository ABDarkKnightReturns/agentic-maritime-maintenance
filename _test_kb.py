import sys
sys.path.insert(0, r'C:\Users\abhis\maritime-maintenance-demo')

from kb.corpus import ALL_CHUNKS
from kb.retriever import kb_retrieve

print(f"Total KB chunks: {len(ALL_CHUNKS)}")

queries = [
    ("turbocharger bearing vibration sub-synchronous oil whirl", "turbocharger", None),
    ("SOLAS starting air compressor minimum starts", "compressor", "regulations"),
    ("pump mechanical seal wear leakage fire risk", "pump", None),
    ("ISO 10816 vibration zone alarm threshold", None, None),
    ("generator insulation resistance megohmmeter test", "generator", "iacs_standards"),
]

for query, asset_type, category in queries:
    results = kb_retrieve(query, asset_type=asset_type, category=category, top_k=2)
    print(f"\n=== {query[:55]}... ===")
    for r in results:
        print(f"  [{r['score']:.3f}] {r['id']}")
        print(f"         {r['text'][:120]}...")
