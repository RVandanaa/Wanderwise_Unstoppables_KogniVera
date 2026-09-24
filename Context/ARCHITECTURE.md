# Architecture — WanderWise

## 1. Overview

```
React Frontend (Vite)                         Multilingual Embedder
 search bar · filter chips                     paraphrase-multilingual-MiniLM-L12-v2
 result cards · explanation line                offline: catalogue · online: query
        │                                              ▲          │
        ▼                                              │ embed    │ offline job
Query Guard — validate filters · empty-pool retry       │ query    │ populates
        │                                              │          ▼ item_embeddings
        ▼                                              │
┌───────────────────────────────────────────────────┐  │
│ FastAPI Backend (single process)                    │  │
│                                                      │  │
│  Hybrid Retrieval          Personalised Reranker     │──┘
│  pgvector sim + SQL         heuristic weights + MMR
│  filters
│
│  Cold-start Fallback       Explanation Generator
│  preferences + popularity   template-filled, score-grounded
│  prior
│
│  Session Profile Store (in-memory, ephemeral)
│  keyed by session_id · nudges rerank score after each click/like/dismiss
└───────────────────────────────────────────────────┘
        │
        ▼  SQL filters + vector similarity
┌───────────────────────────────────────────────────┐
│ Postgres + pgvector                                 │
│ given tables (read as-is): hotels · activities_poi ·│
│ tour_packages · hotel_room_types · cities/countries/ │
│ currencies/languages/categories · users ·            │
│ user_preferences · user_interactions · hotel_reviews │
│ · eval_queries · eval_relevance_labels               │
│                                                       │
│ additive only (Rule R1): item_embeddings (pgvector) ·│
│ hotel_amenity_tags (derived, soft signal)            │
└───────────────────────────────────────────────────┘
```

## 2. Component responsibilities

| Component | Responsibility |
|---|---|
| **React Frontend** | Search bar, filter chips, result cards, explanation line, relaxed/narrow-results banners |
| **Query Guard** | Validates `filters_json` before it reaches SQL (numeric ranges, known `city_id`/`category` values); checks post-retrieval candidate-pool size; retries once with exactly one filter relaxed in a fixed priority order if pool < 5; flags borderline pools (5–9) as `narrow_results: true` without relaxing anything |
| **Hybrid Retrieval** | pgvector cosine similarity over item embeddings, combined with hard SQL filters parsed from `filters_json` |
| **Personalised Reranker** | Heuristic weighted blend of query similarity, profile similarity (explicit + implicit), and a popularity/rating prior; followed by an MMR diversity pass as a second stage inside the same component (not a separate service) |
| **Cold-start Fallback** | For zero-interaction users: `user_preferences` + popularity/rating prior only |
| **Explanation Generator** | Template-fills a one-line reason from whichever score component dominated that item's rank |
| **Session Profile Store** | In-memory, `session_id`-keyed; nudges the rerank score after each click/like/dismiss; does not persist across reloads or devices |
| **Multilingual Embedder** | `paraphrase-multilingual-MiniLM-L12-v2`; embeds the catalogue offline (once) and every incoming query online (per request) into one shared vector space |

## 3. End-to-end flow

1. Traveller submits query + filters (free text in `en-IN`/`hi`/`ta`/`ml`, plus city/price/star/category).
2. Query embedded via the multilingual sentence-transformer, same space as the catalogue.
3. Hybrid retrieval: pgvector similarity + hard SQL filters (city, price, star, category); Query Guard validates filters and retries once on an empty pool.
4. Candidate pool (top ~50) — recall of grade ≥ 2 items is measured here, before rerank.
5. Personalised rerank: query similarity + profile (explicit + implicit) + popularity prior; receives the session profile update from step 9 on subsequent queries in the same session.
6. Explanation generated: template-filled from the dominant score component per item.
7. Ranked results shown to the traveller, each card carrying its one-line "why you're seeing this."
8. Traveller clicks / likes / dismisses — interaction captured with type + item.
9. Session profile updated in-memory — feeds back into step 5 for the next query in the same session.

Steps 8→9→5 form the in-session learning loop: a session's second query is scored with an updated profile, not the one it started with.

## 4. Data placement

- **Everything given** (catalogue, users, preferences, interactions, eval set) lives in Postgres, unmodified.
- **Two additive tables/columns only** (Rule R1 — additive, never repurposing an existing field):
  - `item_embeddings` (pgvector column/table, keyed by `entity_type` + `entity_id`)
  - `hotel_amenity_tags` (derived via keyword extraction on `hotels.description`, negation-checked)
- Nothing in the original 15 given tables is renamed or repurposed.

## 5. Latency budget (enforced, not aspirational)

| Stage | Budget |
|---|---|
| Retrieval | < 300ms |
| Rerank + MMR | < 100ms |
| Explanation fill | < 50ms |
| **End-to-end (server-side)** | **< 600ms** |

Logged during the Block 3 smoke test (see `PLAN.md`). If a stage exceeds budget, the first lever is
cutting candidate-pool size (top-50 → top-20) before touching anything else, since the demo never
shows recall past top-20.

## 6. Deployment shape (hackathon scope, explicitly not production)

Single FastAPI process, single Postgres instance. No caching, load balancing, or multi-instance
deployment — sufficient for a live demo; not claimed as a production architecture.
