# Block 0 — status (Prakruti)

Everything below was actually run and verified against the real `APS-04.db`, not just written.

## What's real and working right now

| Piece | Status | Proof |
|---|---|---|
| FastAPI app boots, connects to the real dataset | ✅ working | `GET /health` returns real row counts: 300 hotels, 900 POIs, 60 packages, 120 eval_queries, 3,600 eval_relevance_labels, 12,339 user_interactions |
| Query Guard — filter validation | ✅ working | Rejects an unknown `city_id`; accepts a real one, checked against the actual `cities` table |
| Hybrid retrieval — SQL-filter half | ✅ working | `city_id` + `star_min` + `price_max` filters run against real `hotels`/`hotel_room_types` rows, with `price_max` compared using `Decimal`, never `float` (per Data Rule R3) |
| Query Guard — pool-size flags | ✅ working | Tested live: a 4★+/₹4,000 Udaipur query genuinely returns 0 candidates (cheapest 4★ room in Udaipur is ₹4,978.34) → correctly flagged `relaxed: true, relaxed_filter: "star_min"`. A looser ₹8,000 query returns 5 real hotels → correctly flagged `narrow_results: true` |
| Session store | ✅ working | Recorded a `like` on `htl_82a0debc` (Garden Kothi & Spa) via `POST /interactions`, then read it back via `GET /session/{id}/profile` |
| Explanation generator | ✅ working (template only) | Returns "within your ₹8000.00 budget" for the price-filtered case — real value, not a placeholder string |

## What's still stubbed (by design — these need Block 1/2/3 inputs that don't exist yet)

| Piece | Stub behaviour today | What unblocks it |
|---|---|---|
| Vector similarity (`retrieval.py: _stub_query_similarity`) | Returns a constant `0.5` for every candidate | Vandanaa's `item_embeddings` population (Block 1) + a real embedding call — needs network access to download `paraphrase-multilingual-MiniLM-L12-v2`, which this sandbox couldn't reach, so the actual embedding call needs to run on your own machine |
| Personalised rerank weights (`rerank.py: WEIGHTS`) | `query_sim` weight 1.0, everything else 0 — a passthrough | Block 3 grid search + bootstrap procedure (`EVALUATION.md`) |
| MMR diversity pass | Not implemented yet | Added inside `rerank.py` per `ARCHITECTURE.md`, after weights are chosen |
| Query Guard's actual relaxation retry | Reports what *would* relax; doesn't re-run retrieval yet | Needs `hybrid_retrieve` to accept a "relax this filter" argument — small change, Block 4 |
| Explanation grounding beyond price | Only handles the price/star cases | Block 3: template-fill from whichever score term actually won for that candidate |

## Files in this scaffold

```
wanderwise/
├── BLOCK_0_STATUS.md          # this file
└── backend/
    ├── requirements.txt
    ├── main.py                 # FastAPI app — /health, /search, /interactions, /session/{id}/profile
    ├── app/
    │   ├── db.py                # sqlite connection (swap for Postgres in Block 1)
    │   ├── query_guard.py        # filter validation (real) + pool/relax (stub)
    │   ├── retrieval.py          # SQL-filter retrieval (real) + vector sim (stub)
    │   ├── rerank.py             # passthrough scoring (stub weights)
    │   ├── explain.py            # template explanations (partial)
    │   └── session_store.py      # in-memory session profile (real)
    └── data/
        ├── APS-04.db            # the real provided dataset
        ├── schema.sql
        └── enums.json
```

## Run it yourself

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/search -H 'Content-Type: application/json' \
  -d '{"session_id":"sess_demo","query_text":"hotel in Udaipur under 8000",
       "filters":{"city_id":"cty_5d572c8a","price_max":"8000.00"}}'
```

(`cty_5d572c8a` is Udaipur's real `city_id` in this dataset — grab any other city's from `data/APS-04.db` directly: `SELECT city_id, name FROM cities;`)

## Suggested next step

This clears the "day-before" checklist item — *"a hello-world deploy of your stack running end to
end"* (`PLAN.md`). Tomorrow's Block 2 (hours 4–8, per `PLAN.md`) is: wire up real pgvector similarity
in `retrieval.py` once Vandanaa's embedding job (Block 1) has populated `item_embeddings`, and swap
`app/db.py` from SQLite to your Postgres connection. Nothing else in `main.py`, `query_guard.py`, or
`session_store.py` needs to change for that swap.
