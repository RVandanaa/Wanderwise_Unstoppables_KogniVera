"""
WanderWise backend — Block 0 scaffold (Prakruti: retrieval, rerank, session
store, Query Guard).

Run: uvicorn main:app --reload --app-dir backend
Then: curl http://127.0.0.1:8000/health
      curl -X POST http://127.0.0.1:8000/search -H 'Content-Type: application/json' \
        -d '{"session_id":"sess_demo","query_text":"hotel in Udaipur","filters":{"city_id":"<a real city_id from /health>"}}'

What's real today: SQLite connection, filter validation against the real
`cities` table, SQL-filter retrieval against real hotels/hotel_room_types
rows, in-memory session store, passthrough rerank, template explanation.

What's stubbed for Block 1-3: vector similarity (retrieval.py), profile-
aware weights (rerank.py), MMR, real explanation grounding, Query Guard's
actual relaxation retry.
"""
from fastapi import FastAPI
from pydantic import BaseModel

from app.db import healthcheck
from app.query_guard import validate_filters, check_pool_and_relax
from app.retrieval import hybrid_retrieve
from app.rerank import rerank
from app.explain import explain
from app.session_store import record_interaction, get_profile

app = FastAPI(title="WanderWise — Block 0 scaffold")


@app.get("/health")
def health():
    counts = healthcheck()
    return {"status": "ok", "db_connected": True, "row_counts": counts}


class SearchRequest(BaseModel):
    session_id: str
    user_id: str | None = None
    query_text: str
    language: str = "en-IN"
    filters: dict = {}
    top_k: int = 10


@app.post("/search")
def search(req: SearchRequest):
    errors = validate_filters(req.filters)
    if errors:
        return {"error": "invalid_filters", "details": errors}

    candidates = hybrid_retrieve(req.query_text, req.filters, limit=50)
    qg = check_pool_and_relax(len(candidates), req.filters)
    ranked = rerank(candidates)[: req.top_k]

    results = [
        {
            "entity_type": c["entity_type"],
            "entity_id": c["entity_id"],
            "name": c["name"],
            "score": c["score"],
            "explanation": explain(c, req.filters),
            "moved_up": None,
        }
        for c in ranked
    ]
    return {"results": results, "query_guard": qg}


class InteractionRequest(BaseModel):
    session_id: str
    user_id: str | None = None
    entity_type: str
    entity_id: str
    interaction_type: str
    position_in_list: int | None = None
    dwell_seconds: int | None = None


@app.post("/interactions")
def interactions(req: InteractionRequest):
    record_interaction(req.session_id, req.entity_id, req.interaction_type)
    return {"status": "recorded", "session_profile_updated": True}


@app.get("/session/{session_id}/profile")
def session_profile(session_id: str):
    return get_profile(session_id)
