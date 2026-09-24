# Block 3 (hours 8–12) — Vandanaa's working checklist

Source: `PLAN.md` Block schedule row 3, `RISKS.md §§ 2, 4`, `EVALUATION.md`
"Amenity-tag quality". Your two pieces this block: cold-start fallback and
amenity tag extraction + spot-check + latency logging. (Rerank, weight grid
search, explanations, and MMR in this same block are Prakruti's — you're
cross-trained on rerank from Block 1, not building it.)

## 0. Hour-8 checkpoint (RISKS.md § 4)

Before anything else in this block:

- [ ] Write the rerank formula down from memory, unaided (blend of query
      similarity + explicit preference + implicit interaction signal +
      popularity prior). If it doesn't come back cleanly, spend a few more
      minutes with Prakruti before starting cold-start work — the whole
      point of Block 1's cross-training was not discovering this gap now.

## 1. Cold-start fallback (`backend/app/cold_start.py`)

- [ ] Verify `POPULARITY_CONFIG` against the real schema — `guest_score` /
      `value_score` are named in `DATA_MODEL.md`, but `tour_packages`'
      rating-equivalent column (`t.rating` here) is an unverified guess
- [ ] Confirm `hotels.guest_score` and `activities_poi.value_score`'s actual
      scale (this assumes 0–10; if it's really 0–5, fix `max_value` in
      `POPULARITY_CONFIG` or every hotel/POI popularity score silently
      halves relative to where it should be)
- [ ] `retrieval.hybrid_retrieve()` (Block 2) doesn't currently select
      `category` or `price` on each candidate — `score_candidates()` reads
      `c.get("category")`/`c.get("price")` and degrades safely to no
      preference-bonus if they're missing, but the fallback is silent. Flag
      to Prakruti whether Block 4's wiring should extend the retrieval
      SELECT so the preference bonus can actually fire
- [ ] Decide with Prakruti whether `is_cold_start_user()` — checking
      `users.segment == 'cold_start'` vs. `user_id is None` (fully
      anonymous) — lives in this file or in Block 4's Query Guard/session
      wiring; this file doesn't decide *when* to call itself, only how to
      score once called
- [ ] Sanity-check the weight split (`W_QUERY_SIM=0.5, W_POPULARITY=0.3,
      W_PREFERENCE=0.2`) against a couple of real cold-start personas by
      hand once data's loaded — these are a plain heuristic, not
      grid-searched (no graded ground truth exists for cold-start,
      `EVALUATION.md`), so "does this look reasonable" is the actual bar

## 2. Amenity tag extraction (`backend/ingestion/extract_amenities.py`)

- [ ] `psql -d wanderwise -f data/migrations/002_hotel_amenity_tags.sql`
- [ ] `python backend/ingestion/extract_amenities.py --dry-run` first —
      read the printed per-hotel tags/drops before writing anything
- [ ] Confirm `AMENITY_KEYWORDS` covers what `eval_queries` actually asks
      for — DATA_MODEL.md names `swimming_pool`, `free_wifi`,
      `step_free_access`, `family_rooms`; re-check that list against the
      real `eval_queries.filters_json` values once loaded, in case there's
      a fifth one
- [ ] Run for real: `python backend/ingestion/extract_amenities.py`
- [ ] Known false-positive risk (found during dry-run testing here): bare
      `"pool"` matches "pool table" / "car pool", not just swimming pools —
      this is exactly what the spot-check below exists to catch, don't
      silently drop the keyword without checking how often it actually
      misfires on the real dataset first

## 3. Manual spot-check (RISKS.md § 2, EVALUATION.md)

Nothing from step 2 is `confirmed = true` yet — extraction only proposes
tags.

- [ ] `python scripts/spot_check_amenities.py --sample 30` — eyeball a
      random 30, per RISKS.md § 2
- [ ] `python scripts/spot_check_amenities.py --amenity step_free_access --confirm` —
      full review of every hotel tagged `step_free_access`, not a sample
      (it's the filter used in the `PRD.md § 4` demo scenario)
- [ ] Any tag you can't confirm by eye: pull it, don't ship it
      (`RISKS.md § 2`, `EVALUATION.md`) — `DELETE FROM hotel_amenity_tags
      WHERE hotel_id = ... AND amenity = ...` for anything wrong that
      `--confirm` didn't already leave unconfirmed

## 4. Latency logging (`backend/app/latency.py`)

- [ ] Hand this to whoever wires the full `/search` pipeline together
      (Block 4) — wrap each stage (`retrieval`, `rerank_mmr`, `explanation`)
      in `Stopwatch.stage()` and call `log_if_over_budget()` after
- [ ] This is scaffolding, not a standalone deliverable — its value only
      shows up once Block 3's smoke test runs the full pipeline end to end

## 5. End-of-block: full-pipeline smoke test (all three, per PLAN.md)

- [ ] ~10 `eval_queries` run by hand through the full pipeline once
      rerank/MMR (Prakruti) and cold-start (you) are both wired in
- [ ] Per-stage latency logged against the budget table
      (`ARCHITECTURE.md § 5`) using `latency.py`
- [ ] Go/no-go: if this smoke test doesn't pass, MMR is the first thing cut
      (`PLAN.md` go/no-go table) — not cold-start, not amenity tags

## 6. What's explicitly NOT in scope here

- The main rerank blend + grid search + MMR pass — Prakruti
- `explain.py`'s real template system — `cold_start.py`'s `explanation`
  field is a placeholder in the same spirit, not the final version
- Confirming *every* amenity tag, only `step_free_access` in full plus a
  30-hotel sample of the rest — matches the stated review scope, not a
  demand for 100% coverage
