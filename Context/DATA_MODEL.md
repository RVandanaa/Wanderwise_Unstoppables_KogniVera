# Data Model — WanderWise

## Rule R1: additive only

Everything given in the 15-table schema is read as-is. WanderWise adds exactly two things beside it,
never renaming or repurposing an existing table or column:

- `item_embeddings` — pgvector column/table, keyed by `entity_type` + `entity_id`. The schema ships
  `CREATE EXTENSION IF NOT EXISTS vector` but no embedding column on any table, so this is added rather
  than repurposing an existing text field.
- `hotel_amenity_tags` — derived, keyword-extracted from `hotels.description`, negation-checked. Several
  `eval_queries` rows ask for amenities (`swimming_pool`, `free_wifi`, `step_free_access`,
  `family_rooms`) but no given table carries structured amenities. This tag set is labelled clearly as
  *inferred, not authoritative*, and used only as a soft rerank signal, never a hard filter.

Plus the (in-memory, not in Postgres) **session profile store** — deliberately ephemeral, since it's
the in-session learning signal, not a durable user record.

## Tables read directly (unmodified, as given)

| Table | Used for |
|---|---|
| `hotels`, `activities_poi`, `tour_packages` | The catalogue itself — retrieval targets, and the `description` text we embed |
| `hotel_room_types` | `base_rate` is the actual price grain for hotels; a hotel's displayed "from" price is `MIN(base_rate)` across its active room types, computed at query time — `hotels` itself has no price column |
| `cities`, `countries`, `currencies`, `languages`, `categories` | Reference joins: city filter, currency display, language tagging, POI/package category taxonomy |
| `users` | Explicit signal — `budget_band`, `travel_style`, `traveller_type`, `segment` (`heavy`/`light`/`cold_start` — this is the literal field the cold-start population is defined by). Read for every request, cold-start or not |
| `user_preferences` | Explicit signal — `interests`, `pace`, `preferred_languages`, `accessibility_needs`, `dietary_flags`, `max_daily_budget` (+ `max_daily_budget_currency`). One row per user (`user_id UNIQUE`). Read for every request, cold-start or not |
| `user_interactions` | Implicit signal for the profile vector — `interaction_type`, `dwell_seconds`, `implicit_rating` where present. `position_in_list` is also read, since offline evaluation that ignores where an item was originally shown overstates the quality of popularity-biased ranking |
| `eval_queries`, `eval_relevance_labels` | The evaluation harness — the one shared ground truth. A fixed, disjoint 20-query slice of `eval_queries` is held out from the final reported metric and used only for weight-tuning, so the reported number is never tuned against itself |
| `hotel_reviews` | Language-diverse text; used only to sanity-check the multilingual embedding space (does a Tamil review of a hotel land near that hotel's English description?), not surfaced directly to the traveller in the MVP |

## What we explicitly do not build on top of the schema

- A structured `amenities` table — doesn't exist in the 15 given tables; see `hotel_amenity_tags` above.
- Booking, payment, or availability logic — `hotel_room_types.total_units` exists for contention
  modelling elsewhere in the data model, but it's a unit count, not a calendar, so date/availability
  filtering is out of scope (see `PRD.md § Deliberately not building`).
- The nine `entity_type`/`target_entity_type` enum values beyond `hotel`, `poi`, and `package` —
  `room_type`, `rate_plan`, `flight`, `flight_fare`, `package_component`, `guide`, `transfer`,
  `event`, `xr_scene` — none of which have `eval_relevance_labels` ground truth in this dataset.

## The eight data rules (apply to every field that came with the dataset)

Source: `data/WORKING_WITH_THE_DATA.md`. These are non-negotiable for anyone touching the given
tables — additive work (our own tables/columns) is exempt.

| # | Rule | What it means for our code |
|---|---|---|
| R1 | Additive only — never rename, drop, or repurpose a given field | `item_embeddings` and `hotel_amenity_tags` sit beside the schema, never inside it |
| R2 | IDs are opaque prefixed strings (`htl_a91f3c`, `usr_0f22b1`, `poi_…`, `pkg_…`) | Never treat an ID as an integer or parse it for meaning; `API_SPEC.md` examples use this format, not UUIDs |
| R3 | Money is a pair: fixed-point decimal (2 places) + ISO-4217 currency code, never a float | `base_rate`, `entry_cost`, `price_max` comparisons must use `Decimal`, never `float()` — a naive CSV/JSON parser is the most common way this breaks |
| R4 | Time is ISO-8601 with an offset; `_at` fields are instants, `_date` fields are zoneless calendar dates | Relevant to `occurred_at` on `user_interactions` |
| R5 | Enums are lowercase snake_case; legal values live in `data/enums.json` | Validate `filters_json` category/theme/segment values against `enums.json`, not a hardcoded list |
| R6 | Language is a BCP-47 tag (`ta`, `hi`, `en-IN`) — never a language name | Matches `PRD.md`/`ARCHITECTURE.md` throughout |
| R7 | Geography is WGS-84 decimal degrees to 6 places; `lat`/`lng` are both present or both absent | Relevant if distance-to-POI ever factors into rerank |
| R8 | Nothing is hard-deleted — mutable rows carry `status` and `updated_at` | Retrieval should filter `status = 'active'` explicitly rather than assuming absence means removed |

## ID prefixes for the tables we read

`cty` cities · `htl` hotels · `rmt` hotel_room_types · `rvw` hotel_reviews · `pkg` tour_packages ·
`usr` users · `prf` user_preferences · `poi` activities_poi · `evq` eval_queries ·
`evl` eval_relevance_labels · `uix` user_interactions · `cat` categories · `cur` currencies ·
`lng` languages · `cnt` countries.

## Language handling

Language is always read as a BCP-47 tag (`en-IN`, `hi`, `ta`, `ml`, plus `bn`/`mr`/`te`/`en-GB` present
in `hotel_reviews`), never inferred or guessed. A query tagged outside the four supported languages
still embeds into the shared vector space and returns a best-effort ranking, but quality is not
claimed or measured for it — a stated limitation, not a tested capability.

## `eval_relevance_labels.grade`, precisely

`grade` is derived, not arbitrary: it counts how many of the query's `filters_json` constraints the
labelled entity misses — 0 misses is grade 3, 1 is grade 2, 2 is grade 1, and a wrong city is grade 0.
About 12% of rows carry deliberate labeller noise, but a grade-3 row always genuinely matches. Useful
to know when debugging why the harness scores a particular result lower than expected.

## Two fields that look derived but are not

- `hotels.guest_score` is a platform aggregate over more reviews than the 25 visible per hotel in
  `hotel_reviews`. It correlates with the mean of `hotel_reviews.rating` (r ≈ +0.67) but is not
  computed from it — don't expect them to reconcile row by row.
- `activities_poi.value_score` is an editorial rating, not a function of price, popularity, or duration.

## `user_interactions` — full field set actually in the schema

`interaction_type` legal values: `view`, `click`, `like`, `save`, `book`, `dismiss`, `share`,
`search` (the rerank blend weights `like`/`save`/`book` above `view`/`click`; `share`/`search` are
read but not currently weighted — worth a look if time allows). Each row also carries `channel`
(`web`/`mobile_app`/`partner`/`call_centre`/`agent`), and its own historical `session_id`,
`query_text`, and `query_language` — distinct from WanderWise's own live, in-memory session store,
which starts fresh per browser session rather than reading these historical session IDs back.
