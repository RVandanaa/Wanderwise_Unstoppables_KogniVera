# API Spec — WanderWise Backend

FastAPI, single process. All endpoints JSON in / JSON out. This spec derives the concrete contracts
implied by the design document's flow (`ARCHITECTURE.md § 3`); adjust field names to match the final
Pydantic models during implementation.

**ID and money format — matches the dataset's own rules (Data Rules R2/R3, `DATA_MODEL.md`)**: every
ID below is an opaque prefixed string (`htl_…`, `usr_…`, `poi_…`, `pkg_…`, `cty_…`) exactly as given
in the CSVs/DB — never an integer, never a UUID, never parsed for meaning. Every money value is a
2-decimal-place **string**, never a JSON number — `"4000.00"`, not `4000` — parse with `Decimal`,
never `float()`, on both sides of the API boundary.

## `POST /search`

Runs the full pipeline: Query Guard → hybrid retrieval → personalised rerank → MMR → explanation.

**Request**
```json
{
  "session_id": "sess_7f2a91",
  "user_id": "usr_0f22b1",
  "query_text": "4-star hotel in Udaipur, under ₹4,000/night",
  "language": "en-IN",
  "filters": {
    "city_id": "cty_a1b2c3",
    "price_max": "4000.00",
    "star_min": 4,
    "category": null,
    "amenities": ["step_free_access"]
  },
  "top_k": 10
}
```

**Response**
```json
{
  "results": [
    {
      "entity_type": "hotel",
      "entity_id": "htl_a91f3c",
      "name": "Lakeview Guesthouse",
      "score": 0.87,
      "explanation": "within your ₹4,000 budget",
      "moved_up": null
    }
  ],
  "query_guard": {
    "relaxed": false,
    "relaxed_filter": null,
    "narrow_results": false,
    "candidate_pool_size": 42
  },
  "latency_ms": {
    "retrieval": 210,
    "rerank_mmr": 65,
    "explanation": 18,
    "total": 293
  }
}
```

**Query Guard behaviour** (see `ARCHITECTURE.md`, `RISKS.md`):
- Validates `filters` before SQL (numeric ranges, known `city_id`/`category` values).
- If candidate pool < 5: retries once with exactly one filter relaxed, fixed priority order
  `star_min` → `category` → `price_max`. `city_id` is never auto-relaxed. Response carries
  `relaxed: true` and names the relaxed filter.
- If candidate pool is 5–9 (clears the relaxation trigger but still thin): response carries
  `narrow_results: true`, nothing is silently loosened.

## `POST /interactions`

Records a click / like / dismiss / save / book event and updates the in-memory session profile.

**Request**
```json
{
  "session_id": "sess_7f2a91",
  "user_id": "usr_0f22b1",
  "entity_type": "hotel",
  "entity_id": "htl_a91f3c",
  "interaction_type": "like",
  "position_in_list": 2,
  "dwell_seconds": 12
}
```

**Response**
```json
{ "status": "recorded", "session_profile_updated": true }
```

`interaction_type` legal values (per `data/enums.json`, same enum used by the given
`user_interactions` table): `view`, `click`, `like`, `save`, `book`, `dismiss`, `share`, `search`.
`like`/`save`/`book` are weighted above `view`/`click` in the implicit profile vector per
`ARCHITECTURE.md`; `share`/`search` are recorded but not currently weighted. This is WanderWise's
own live session-write endpoint — separate from the historical `session_id` already present on each
`user_interactions` row in the dataset (`DATA_MODEL.md`), which the eval/cold-start-masking code
reads but the live app does not write to.

## `GET /session/{session_id}/profile`

Debug/inspection endpoint — returns the current in-memory session profile vector and the
interactions that fed it. Not called by the frontend in the normal flow; useful for the in-session
demo script (`PLAN.md`, Block 6).

**Response**
```json
{
  "session_id": "sess_7f2a91",
  "interaction_count": 3,
  "profile_vector_summary": { "liked_entities": ["htl_a91f3c"], "dismissed_entities": [] }
}
```

## `GET /health`

Liveness/readiness check, used by the Block 3 smoke test and pre-demo warm-up.

**Response**
```json
{ "status": "ok", "embedding_model_loaded": true, "db_connected": true }
```

## Notes

- No authentication scope is defined for the hackathon MVP; `user_id` is optional and its absence
  routes the request through the cold-start path (`user_preferences` + popularity prior only, or a
  pure popularity/rating prior with no preferences for a fully anonymous session).
- The soft-constraint LLM extraction (stretch, `PRD.md § 3`) is not a separate endpoint — it's an
  internal step inside `/search` that runs only when the stretch feature is greenlit (hour-18
  checkpoint) and degrades silently to the Block 2 filter parser on low confidence or timeout.
- The evaluation harness (`EVALUATION.md`) calls the same pipeline code as `/search`, not a parallel
  implementation, so reported metrics can't silently drift from what's deployed.
