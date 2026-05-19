"""
Offline TF-IDF retriever for the maritime knowledge base.
No internet or model downloads required — uses scikit-learn (standard Anaconda package).

Usage:
    from kb.retriever import kb_retrieve
    results = kb_retrieve("turbocharger bearing vibration sub-synchronous", top_k=3)
"""
from __future__ import annotations
import json
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from kb.corpus import ALL_CHUNKS


# ── Build index once at module load ───────────────────────────────────────────

@lru_cache(maxsize=1)
def _build_index():
    """Fits TF-IDF vectorizer on entire corpus. Called once; cached."""
    docs = [chunk["text"] for chunk in ALL_CHUNKS]
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),       # unigrams + bigrams capture "ISO 10816", "SOLAS II-1" etc.
        min_df=1,
        max_df=0.9,
        sublinear_tf=True,        # log(1+tf) — reduces weight of very frequent terms
        strip_accents="unicode",
        lowercase=True,
    )
    matrix = vectorizer.fit_transform(docs)
    return vectorizer, matrix


# ── Public retrieval function ─────────────────────────────────────────────────

def kb_retrieve(
    query: str,
    asset_type: str | None = None,
    category: str | None = None,
    top_k: int = 3,
) -> list[dict]:
    """
    Retrieve top-k knowledge base chunks relevant to query.

    Args:
        query:      Free-text query (e.g. "bearing failure vibration rising")
        asset_type: Optional filter — "pump", "compressor", "turbocharger", "purifier",
                    "generator", or None for all assets
        category:   Optional filter — "failure_modes", "maintenance_intervals",
                    "regulations", "iacs_standards", "troubleshooting"
        top_k:      Number of results to return

    Returns:
        List of dicts with keys: id, text, metadata, score
    """
    if not query or not query.strip():
        return []

    vectorizer, matrix = _build_index()

    # Determine which chunks are candidates (apply filters)
    candidates = []
    candidate_indices = []
    for i, chunk in enumerate(ALL_CHUNKS):
        meta = chunk.get("metadata", {})
        if asset_type and asset_type.lower() not in (meta.get("asset_type", ""), "all"):
            continue
        if category and category != meta.get("category", ""):
            continue
        candidates.append(chunk)
        candidate_indices.append(i)

    if not candidates:
        return []

    # Vectorize query
    query_vec = vectorizer.transform([query])

    # Compute cosine similarity only against candidate rows
    candidate_matrix = matrix[candidate_indices]
    scores = cosine_similarity(query_vec, candidate_matrix)[0]

    # Rank and return top_k
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        score = float(scores[idx])
        if score < 0.01:   # skip near-zero matches
            continue
        chunk = candidates[idx]
        results.append({
            "id":       chunk["id"],
            "text":     chunk["text"],
            "metadata": chunk["metadata"],
            "score":    round(score, 4),
        })

    return results


def kb_retrieve_formatted(
    query: str,
    asset_type: str | None = None,
    category: str | None = None,
    top_k: int = 3,
) -> str:
    """Returns JSON string suitable for returning as a tool result."""
    results = kb_retrieve(query, asset_type=asset_type, category=category, top_k=top_k)
    if not results:
        return json.dumps({"query": query, "results": [], "note": "No relevant knowledge found"})
    return json.dumps({
        "query":   query,
        "results": [
            {
                "id":     r["id"],
                "source": r["metadata"].get("source", ""),
                "topic":  r["metadata"].get("topic", ""),
                "text":   r["text"],
                "relevance_score": r["score"],
            }
            for r in results
        ],
        "total_found": len(results),
    }, indent=2)
