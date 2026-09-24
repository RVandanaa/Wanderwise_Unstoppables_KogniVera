# Block 1 (hours 0–4) — Vandanaa's working checklist

Source: `PLAN.md` Block schedule row 1, `RISKS.md § 4`.

## 1. Schema + data load

- [ ] `createdb wanderwise`
- [ ] `psql -d wanderwise -f data/schema.sql` (the given schema — read-only, never edit)
- [ ] Load `data/csv/*.csv` **in numbered order** (foreign keys resolve as you go)
- [ ] `python3 tools/validate_conformance.py data/APS-04.db` — must pass before continuing.
      This is part of the official data package, not something we write ourselves.
- [ ] `psql -d wanderwise -f data/migrations/001_item_embeddings.sql`
      (this repo's file — additive only, Rule R1)

## 2. Verify TABLE_CONFIG against the real schema

`backend/ingestion/embed_catalogue.py`'s `TABLE_CONFIG` guesses column names
(`hotel_id`, `poi_id`, `package_id`, `description`, `status`) from what
`DATA_MODEL.md` says each table is used for — it was written before the real
`data/schema.sql` was in this checkout. Before running the embedding job:

- [ ] Open the real `data/schema.sql`, confirm the id/description/status
      column names for `hotels`, `activities_poi`, `tour_packages`
- [ ] Fix `TABLE_CONFIG` in `embed_catalogue.py` if anything differs
- [ ] Confirm the `status` enum's active value is literally `'active'`
      (check `data/enums.json` per Rule R5 — don't assume)

## 3. Run the embedding job

- [ ] `pip install -r requirements.txt`
- [ ] `cp .env.example .env` and fill in local Postgres credentials
- [ ] `python backend/ingestion/embed_catalogue.py`
- [ ] `python backend/ingestion/check_embeddings.py` — confirm zero NULL
      embeddings and all three entity types present
- [ ] Spot-check one row per entity type by hand: does the embedded
      `description` text actually look right for that row?

## 4. While the embedding job runs unattended (Risk 4 mitigation)

The embedding job is the one part of Block 1 that doesn't need Vandanaa
watching it continuously. `RISKS.md § 4` uses that time for cross-training,
not idle waiting:

- [ ] Sit with Prakruti through the rerank formula (blend weights over query
      similarity + explicit preference + implicit interaction signal) —
      enough to re-derive it from memory, not just recognise it
- [ ] Sit with Prakruti through the cold-start fallback logic she owns from
      Block 3 (`user_preferences` + popularity/rating prior lookup — the
      simplest of the five backend pieces per `RISKS.md § 4`)
- [ ] **Hour-8 checkpoint**: try writing the rerank formula down from memory,
      unaided, before Block 3 starts. If it doesn't come back cleanly, that's
      what the rest of Block 1's slack goes to — not discovering the gap
      mid-Block-3.

## 5. End-of-block state (hands off to Block 2 / Prakruti)

- [ ] `item_embeddings` fully populated, `check_embeddings.py` passing
- [ ] Conformance check passing
- [ ] Rerank formula + cold-start logic understood well enough to debug or
      take over either one
- [ ] Nothing here blocks Prakruti's Block 2 retrieval work — she reads
      `item_embeddings` directly, no hand-off meeting needed
