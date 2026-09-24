"""
main.py — FastAPI entrypoint.

Block 2 scope only: `/health` and a `/search` that runs hybrid retrieval and
returns it directly, sorted by similarity, with no personalised rerank, no
MMR, and no Query Guard relaxation/retry yet. Those land in Block 3 and
Block 4 respectively (`PLAN.md`) — this file has explicit TODO markers at
each seam so it's obvious what to wire in and where.

Run: `uvicorn backend.main:app --reload` (per README.md "Running locally").
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException

# app/ modules import each other with bare names (e.g. `from query_embedder
# import ...`) rather than package-relative imports, so this path needs to
# be importable both when run as `uvicorn backend.main:app` from the repo
# root and when a script under backend/app/ or scripts/ is run directly.
sys.path.insert(0, str(Path(__file__).parent / "app"))

import db  # noqa: E402
import query_embedder  # noqa: E402
import retrieval  # noqa: E402
from schemas import (  # noqa: E402
    LatencyBreakdown,
    QueryGuardInfo,
    SearchRequest,
    SearchResponse,
)

app = FastAPI(title="WanderWise", version="0.2.0")  # 0.2 = through Block 2


@app.on_event("startup")
def on_startup():
    db.init_pool()
    query_embedder.warm_up()  # RISKS.md § 5, § 8 — pay the model-load cost once, at startup


@app.get("/health")
def health():
    db_ok = True
    try:
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "embedding_model_loaded": query_embedder._model is not None,
        "db_connected": db_ok,
    }


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    # TODO(Block 4, Query Guard): validate req.filters before this point —
    # numeric ranges, known city_id/category values against enums.json —
    # and handle the empty-pool retry / narrow_results flag. None of that
    # exists yet, so a bad filter currently surfaces as a 500 from Postgres
    # (undefined city, etc.) rather than a clean 4xx. Known gap, not a bug.

    filters = req.filters.model_dump()

    t0 = time.perf_counter()
    try:
        with db.connection() as conn:
            candidates = retrieval.hybrid_retrieve(
                conn,
                query_text=req.query_text,
                filters=filters,
                top_k=max(req.top_k, retrieval.DEFAULT_TOP_K),
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"retrieval failed: {e}") from e
    retrieval_ms = int((time.perf_counter() - t0) * 1000)

    # TODO(Block 3): replace this with the personalised rerank + MMR pass.
    # For now, "rank" is just retrieval similarity, and every result's
    # `explanation` says so plainly rather than fabricating a reason a
    # rerank step hasn't actually computed yet.
    top_results = candidates[: req.top_k]
    results = [
        {
            "entity_type": c["entity_type"],
            "entity_id": c["entity_id"],
            "name": c["name"],
            "score": round(float(c["similarity"]), 4),
            "explanation": "retrieval similarity only — rerank not yet wired in (Block 3)",
            "moved_up": None,
        }
        for c in top_results
    ]

    return SearchResponse(
        results=results,
        # TODO(Block 4): real Query Guard output — relaxation, narrow_results.
        query_guard=QueryGuardInfo(
            relaxed=False,
            relaxed_filter=None,
            narrow_results=len(candidates) < 10,  # placeholder threshold, not the real Query Guard logic
            candidate_pool_size=len(candidates),
        ),
        latency_ms=LatencyBreakdown(
            retrieval=retrieval_ms,
            rerank_mmr=0,
            explanation=0,
            total=retrieval_ms,
        ),
    )
