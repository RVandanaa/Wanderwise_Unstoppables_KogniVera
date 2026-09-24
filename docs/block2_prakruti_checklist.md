# Block 2 (hours 4–8) — Prakruti's working checklist

Source: `PLAN.md` Block schedule row 2, go/no-go checkpoint table.

## Prerequisites (should already be true from Block 1)

- [ ] `item_embeddings` populated — confirm with
      `python backend/ingestion/check_embeddings.py`
- [ ] Rerank formula + cold-start logic cross-trained with Vandanaa
      (`RISKS.md § 4`, hour-8 checkpoint)

## 1. Verify assumptions before trusting retrieval.py

Same caveat as Block 1's `embed_catalogue.py`: `backend/app/retrieval.py`'s
`ENTITY_CONFIG` guesses column names because the real `data/schema.sql`
wasn't in this checkout when it was written.

- [ ] Confirm `hotel_room_types.base_rate` / `status` column names against
      the real schema (used in the hotel price subquery)
- [ ] Confirm `activities_poi.entry_cost` is the real column name
- [ ] Find and fix `tour_packages`' actual price column — `t.price` in
      `ENTITY_CONFIG["package"]["price_expr"]` is an unverified placeholder
- [ ] Confirm `activities_poi`/`tour_packages` both have a `category_id` FK
      to `categories`, and that `categories.code` is the right column to
      match `filters.category` against
- [ ] Decide whether hotels should ever match a `category` filter (this
      file currently excludes hotels entirely from any query with
      `category` set — confirm that's actually the intended MVP behaviour,
      not just this file's guess)

## 2. Run it

- [ ] `pip install -r requirements.txt` (adds fastapi/uvicorn/pydantic to
      Block 1's deps)
- [ ] `uvicorn backend.main:app --reload`
- [ ] `curl localhost:8000/health` — expect `db_connected: true`,
      `embedding_model_loaded: true` (the startup warm-up should already
      have loaded it — RISKS.md § 5, § 8)
- [ ] `curl -X POST localhost:8000/search -d '{...}'` against the
      `PRD.md § 4` Meera/Udaipur scenario — the one flow the whole demo
      hangs on, so it's worth checking here first, not just at Block 4

## 3. Go/no-go checkpoint (end of Block 2)

`PLAN.md`: "Hybrid retrieval returns correct results for 5 hand-checked
`eval_queries`." Support script:

- [ ] `python scripts/validate_retrieval.py --n 5`
- [ ] For each of the 5, eyeball: do the top results actually look right
      for that query text + filters? Are the query's grade-3
      `eval_relevance_labels` rows showing up in the pool at all?
- [ ] If this fails: per the go/no-go table, Block 3's time budget shrinks
      to protect Block 4/5 — don't silently absorb the slip into Block 3

## 4. What's explicitly NOT in scope for Block 2

Left as TODOs in `backend/main.py`, don't build them here:

- Personalised rerank + MMR (Block 3)
- Query Guard validation, empty-pool retry, `narrow_results` (Block 4) —
  right now a bad filter value 500s instead of a clean 4xx; known gap
- Explanation generation beyond the placeholder string
- `/interactions` and `/session/{id}/profile` endpoints (Block 4)

## 5. End-of-block state (hands off to Block 3)

- [ ] `/search` returns a similarity-ranked candidate pool for a real query
- [ ] Per-stage latency logged at least informally — `latency_ms.retrieval`
      is already in the response; watch it against the < 300ms budget
      (`ARCHITECTURE.md § 5`) so Block 3 isn't the first time it's measured
- [ ] `retrieval.hybrid_retrieve()` signature is stable — Block 3's rerank
      code and Block 5's harness (`EVALUATION.md § Harness implementation
      note`) both call it directly, not a reimplementation
