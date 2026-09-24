# WanderWise — Hyper-Personalised Recommendation Engine

**Kognivera Hackathon 2026 · Team UNSTOPABLES**

| Role | Name | Responsibility |
|---|---|---|
| Backend & AI | Prakruti | Hybrid retrieval, personalised rerank & MMR, session store & Query Guard |
| Frontend | Pranav | Search/filter/result UI, wireframes, multilingual query input, Query Guard filter-validation pairing |
| Data & Evaluation | Vandanaa | Schema load, embedding & amenity-tag pipelines, cold-start fallback, evaluation harness, NDCG/precision run |

## What this is

WanderWise turns a free-text travel query (English, Hindi, Tamil, or Malayalam) into a ranked,
personalised list of hotels, POIs, and tour packages. It combines vector-similarity retrieval with
hard SQL filters, re-ranks using a blend of query similarity + explicit preferences + implicit
interaction history, diversifies the final list with MMR, and explains every result in one line.

See `PRD.md` for the full problem statement and scope, `ARCHITECTURE.md` for how the system fits
together, and `PLAN.md` for the 24-hour build schedule.

## Project docs

| Doc | Contents |
|---|---|
| [`PRD.md`](./PRD.md) | Problem, users, scope (MVP / stretch / deliberately-not-building), success criteria |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | System diagram, component responsibilities, latency budget |
| [`DATA_MODEL.md`](./DATA_MODEL.md) | Tables read as-is, additive tables, and the rules governing them |
| [`API_SPEC.md`](./API_SPEC.md) | Endpoint contracts for retrieval, rerank, interactions, and session state |
| [`EVALUATION.md`](./EVALUATION.md) | Metrics, weight-tuning methodology, reported numbers |
| [`RISKS.md`](./RISKS.md) | Named risks, fallbacks, and the tiered cut list |
| [`PLAN.md`](./PLAN.md) | Hour-by-hour build plan, owners, go/no-go checkpoints |

## Who reads what

Everyone should skim `PRD.md` and `ARCHITECTURE.md` once — they're the shared mental model. Beyond
that, read in this order for your own piece:

| Person | Owns | Read first | Also needed |
|---|---|---|---|
| **Prakruti** (Backend & AI) | Hybrid retrieval, rerank + MMR, session store, Query Guard | `ARCHITECTURE.md`, `API_SPEC.md` | `DATA_MODEL.md` (what to read from Postgres), `EVALUATION.md § Weight selection` (how your blend weights get chosen), `RISKS.md §§ 4, 5` (your ownership load + latency budget) |
| **Pranav** (Frontend) | Search/filter/result UI, wireframes, multilingual input, Query Guard's filter-validation half | `API_SPEC.md` (esp. `POST /search` request/response shape), `PRD.md § 4` (user journey → what each screen shows) | `RISKS.md § 6` (`narrow_results` banner), `PLAN.md` Block 4 (your pairing with Prakruti on Query Guard) |
| **Vandanaa** (Data & Evaluation) | Schema load, embedding + amenity pipelines, cold-start fallback, evaluation harness | `DATA_MODEL.md`, `EVALUATION.md` | `RISKS.md §§ 1, 2, 3, 7` (language coverage, amenity negation checks, cold-start ground truth, harness cut list) |

`PLAN.md` and `RISKS.md` are shared — both are written as a single hour-by-hour source of truth
rather than split per person, since the go/no-go checkpoints and cut list depend on all three blocks.

## Interface handoffs between roles

These are the exact contracts each person's work depends on from someone else's — the place a
mismatch would actually break integration. Everything else in the docs is background.

**Pranav → Prakruti** (frontend sends, backend consumes): the `filters` object inside the
`POST /search` request body — `city_id`, `price_max`, `star_min`, `category`, `amenities` — see
`API_SPEC.md § POST /search`. This is the shape Query Guard validates, so if the frontend changes a
filter's name or type, Query Guard's validation and the fixed relaxation order (`RISKS.md § 6`,
`ARCHITECTURE.md § 2`) need to change with it.

**Prakruti → Pranav** (backend sends, frontend renders): the `POST /search` response —
`results[]` (each with `explanation` and optional `moved_up`), and the `query_guard` block
(`relaxed`, `relaxed_filter`, `narrow_results`, `candidate_pool_size`). The frontend's relaxed-filter
banner (Screen 3, `PRD.md § 4`) and narrow-results notice (`RISKS.md § 6`) both read directly off
`query_guard`, not off inferring it from result count.

**Vandanaa → Prakruti** (data pipeline produces, backend reads at query time): `item_embeddings`
(keyed by `entity_type` + `entity_id`) and `hotel_amenity_tags` (soft signal only, never a hard
filter) — see `DATA_MODEL.md § Rule R1`. Prakruti's retrieval and rerank code assumes both are
already populated; if the embedding or amenity job hasn't finished, retrieval falls back to SQL
filters alone with no ranking signal.

**Prakruti → Vandanaa** (backend pipeline, evaluation harness calls it directly): the harness in
`eval/run_harness.py` must call the same retrieval+rerank+MMR code path as `/search`, not a
reimplementation — see `EVALUATION.md § Harness implementation note`. If Prakruti changes a function
signature in `backend/app/`, the harness call site needs updating in the same PR.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python) |
| Database | Postgres + pgvector |
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers) |
| Rerank | Hand-tuned heuristic scorer, grid-searched weights + MMR diversity pass |
| Frontend | React (Vite) |
| Evaluation | Python script against `eval_queries` / `eval_relevance_labels` |
| Soft-constraint extraction (stretch) | Single small LLM call, confidence-gated |

## Repo structure (proposed)

```
wanderwise/
├── backend/
│   ├── app/
│   │   ├── retrieval.py        # pgvector similarity + SQL filters
│   │   ├── rerank.py           # heuristic blend + MMR pass
│   │   ├── query_guard.py      # filter validation + empty/borderline-pool handling
│   │   ├── explain.py          # template-filled explanation generator
│   │   ├── session_store.py    # in-memory session profile
│   │   └── cold_start.py       # preferences + popularity-prior fallback
│   ├── ingestion/
│   │   ├── embed_catalogue.py  # populates item_embeddings
│   │   └── extract_amenities.py# keyword + negation-checked hotel_amenity_tags
│   └── main.py                 # FastAPI app entrypoint
├── frontend/                   # React (Vite) — search bar, filter chips, result cards
├── eval/
│   └── run_harness.py          # NDCG@10 / precision@10 over eval_queries
├── data/
│   └── schema.sql              # given schema (read-only) + additive tables
└── docs/                       # this folder
```

## Running locally (outline)

Uses the official `APS-04_Recommendations` data package (SQLite `data/APS-04.db`, CSVs, and
`data/schema.sql`) as the source of truth for tables, IDs, and enums — see `DATA_MODEL.md` for the
conventions (opaque prefixed IDs, money as decimal strings, BCP-47 language tags, etc.).

1. Fastest path to a first query: `sqlite3 APS-04.db < data/queries/starter_queries.sql` — no setup.
2. To build against Postgres: `createdb wanderwise && psql -d wanderwise -f data/schema.sql`, then
   load each `data/csv/*.csv` in its numbered order (foreign keys resolve as you go).
3. `CREATE EXTENSION IF NOT EXISTS vector;` (idempotent, already in schema).
4. `python3 tools/validate_conformance.py data/APS-04.db` — run this early and again after any data
   changes; it checks ID prefixes, enum legality, money format, and FK resolution.
5. `python backend/ingestion/embed_catalogue.py` — populates `item_embeddings`.
6. `python backend/ingestion/extract_amenities.py` — populates `hotel_amenity_tags`.
7. `uvicorn backend.main:app --reload`
8. `cd frontend && npm install && npm run dev`
9. `python eval/run_harness.py` — reproduces the reported NDCG@10 / precision@10 numbers.

## Scope note

This MVP deliberately excludes flights, transfers, guides, events, rate plans, XR scenes, booking/
payment logic, and a structured amenities table — see `PRD.md § Deliberately not building` for why.
WanderWise is not an AR/VR submission (`hotels.has_xr_scene` / `activities_poi.has_xr_scene` are not used).
