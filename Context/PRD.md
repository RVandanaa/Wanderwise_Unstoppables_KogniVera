# PRD — WanderWise Hyper-Personalised Recommendation Engine

**Kognivera Hackathon 2026 · Team UNSTOPABLES (Prakruti, Pranav, Vandanaa)**

## 1. Problem statement

Two travellers can type the same keyword query — "budget hotel in Udaipur" — and want genuinely
different things: one is travelling with parents and needs step-free access, the other is a solo
backpacker chasing the cheapest bed near the station. Keyword-only matching can't tell them apart;
hard filters alone get constraints right but ordering wrong, because they carry no notion of who is
asking.

WanderWise requires both halves at once:
- **Retrieval** that understands query meaning (embeddings) and respects explicit constraints (structured filters).
- **Ranking** that adapts to the person asking, using both stated preferences and interaction history.
- **Explainability** — every recommendation states why it's there.
- **Cold-start quality** — a brand-new user gets better than a random shuffle.
- **In-session adaptation** — the list visibly improves as the traveller clicks around.
- **Multilingual support** — English, Hindi, Tamil, Malayalam queries, one shared embedding space.
- **Proof, not a feeling** — Precision@k / NDCG@k against a shared, graded evaluation set, **reported
  for two configurations (retrieval-only vs. retrieval+rerank) with the delta stated — see
  `EVALUATION.md § Mandatory enhancement`.** This is a scored requirement, not a stretch: the harness
  must run live, in front of a judge, on `eval_queries`/`eval_relevance_labels`.

## 2. Target users

- Travellers issuing free-text + filter search queries in `en-IN`, `hi`, `ta`, or `ml`.
- Includes travellers booking on behalf of others (e.g. elderly parents) who weight *why* a result
  was surfaced as much as the result itself.
- Roughly half the seeded user base (600 / 1,200 users) has zero interaction history — cold start is
  not an edge case, it's half the population.

## 3. Scope

### In scope (MVP, built in 24 hours)
- Seeded catalogue (hotels, activities/POIs, tour packages) with multilingual sentence embeddings in Postgres + pgvector.
- Hybrid retrieval: pgvector cosine similarity + at least two hard SQL filters (`city_id`, and one of `price_max` / `star_min` / POI `category`).
- **Query Guard**: validates `filters_json` before it reaches SQL; retries once with exactly one filter relaxed (fixed priority order) if the candidate pool is under 5; flags a distinct `narrow_results: true` case for pools of 5–9.
- Heuristic personalised reranker blending query similarity, explicit-preference match, and an implicit profile vector from `user_interactions`.
- Diversity-aware final selection via a Maximal-Marginal-Relevance (MMR) pass.
- Cold-start fallback: explicit preferences + popularity/rating prior for the 600 zero-interaction users.
- In-session learning: an in-memory, `session_id`-keyed store that nudges rerank score after each click/like/dismiss.
- Per-item, one-line "why you're seeing this" explanation, grounded in the actual matched signal.
- Multilingual queries across `en-IN`, `hi`, `ta`, `ml` in one shared embedding space.
- Per-stage latency budget, logged and enforced (build requirement, not a reported metric).

### Stretch (built only if time permits — go/no-go at hour 18)
- LLM-assisted soft-constraint extraction: a single, confidence-gated LLM call extracts free-text soft
  constraints ("quiet, away from the main market") as soft tags feeding the existing rerank score.
  Never introduces new hard SQL filters. Falls back silently to the Block 2 parser below a confidence
  threshold or a 150ms budget.

### Deliberately not building
- Flights, transfers, guides, events, rate plans, XR scenes, package components — no graded ground
  truth exists for these `entity_type` values in `eval_relevance_labels`.
- A learned (trained) reranker — no time to validate a train/test split in 24 hours; an unvalidated
  model that underperforms a transparent heuristic is a worse outcome.
- A structured `amenities` table — doesn't exist in the given schema; amenity tags are derived via
  keyword extraction and used only as a soft rerank signal, never a hard filter.
- A cold-start precision/NDCG number — none of the 120 `eval_queries` are pinned to a `cold_start`
  persona, so there's no graded ground truth to score against. Demoed live instead.
- Cross-device or persisted session state — in-session learning lives in memory for the session's lifetime only.
- Booking, payment, or availability logic.
- Caching, load balancing, multi-instance deployment — single FastAPI process, single Postgres instance.

## 4. User journey (reference scenario)

Meera is planning a trip to Udaipur for her parents: 4-star-and-up, under ₹4,000/night, step-free access.

1. **First search** — no history yet, so results rank by her onboarding preferences (interests,
   budget) + a popularity/rating prior. Every card carries a one-line reason (e.g. "within your
   ₹4,000 budget").
2. **After one "like"** — without a page reload, her next search in the same session visibly
   reorders; a similar property moves up and its explanation updates ("similar to Lakeview
   Guesthouse, which you liked").
3. **Over-constrained query** — a 5-star request under ₹2,500 returns fewer than 5 candidates; Query
   Guard relaxes star rating first (fixed priority order), flags the response `relaxed: true`, and
   every affected card explains what changed. Location is never auto-relaxed.

## 5. Success criteria / metrics

- **Headline metric**: NDCG@10 (primary; labels are graded 0–3) and precision@10 (for readability),
  computed by running the actual retrieval+rerank pipeline against all 120 `eval_queries` scored
  against `eval_relevance_labels`, broken down by language and by intent.
- **Personalisation delta**: NDCG@10 / precision@10 on the 94 persona-linked queries, rerank vs. a
  matched retrieval-only baseline — isolates what the rerank step buys, separate from the headline number.
- **Target**: a positive, double-digit-percent relative improvement in NDCG@10 on the 94 persona-linked queries — reported as a target, as-measured, even if the real number lands lower.
- **Retrieval quality**: recall of the labelled-relevant set (grade ≥ 2) within the top-50 candidate pool, before rerank runs, per target entity type.
- **Diversity**: intra-list average pairwise embedding-cosine-similarity within the top-10, before vs. after MMR, with the explicit trade-off against NDCG@10 reported alongside.
- **Explanation quality**: manual spot-check pass — is the stated reason the actual dominant score component? (Not NDCG-measured; called out explicitly as such.)

Full evaluation methodology: see `EVALUATION.md`.

## 6. Business benefits

**For the traveller**: less scrolling past irrelevant results, filters that are actually respected,
a stated reason for every recommendation, and (stretch) plain-language soft constraints ("quiet",
"walkable to the lake") captured without a form field.

**For the business**: personalisation from the first session (no multi-week behavioural warm-up),
a measured relevance number tracked over time and by language, and multilingual *query* support
(not just multilingual content) reaching travellers who'd otherwise fall back to unranked keyword
search.

**Magnitude, sized against this dataset**:
- Cold start is half the user base (600 / 1,200 users, zero interaction rows).
- Non-English demand is a third of measured query volume (40 / 120 `eval_queries` are `hi`/`ta`/`ml`).

## 7. What's distinctive

- Weight selection validated by bootstrap resampling, not a single grid-search pass (see `EVALUATION.md`).
- An MMR diversity layer shipped conditionally on a measured NDCG trade-off, not always-on by assertion.
- A confidence-gated LLM extraction that degrades to a fully working system on failure, rather than being a dependency.
- Every ranking decision traces to a named score term a judge can question live — no black-box reranker.

## 8. Requirement checklist (brief → deliverable)

| Brief requirement | Satisfied by |
|---|---|
| User profile: implicit + explicit feedback | `user_preferences` (explicit, always read) + `user_interactions`-derived implicit vector |
| Hybrid retrieval: embeddings + structured filters | pgvector similarity + `city_id`/`price_max`/`star_min`/category SQL filters |
| Personalised reranking | Heuristic blend (grid-searched weights) + MMR diversity pass |
| Per-item explanations | Template-filled, grounded in the dominant score term |
| Cold-start handling | Preferences + popularity prior for zero-interaction users |
| In-session updates | In-memory session store feeding the next rerank call |
| Multilingual content and queries | One shared multilingual embedding space, `en-IN`/`hi`/`ta`/`ml` |
| Reported relevance metric | NDCG@10 + precision@10, per-language and per-intent, against all 120 `eval_queries`, with a retrieval-only baseline |
| **Mandatory enhancement — Ablation Report** (two configs + delta, live for the judge) | `eval/run_ablation.py` — retrieval-only vs. retrieval+rerank on the 94 persona-linked queries, delta stated and explained honestly even if negative — see `EVALUATION.md § Mandatory enhancement` |
| Seeded catalogue with embeddings + attributes | Offline embedding job over hotels/activities_poi/tour_packages |
| Results "feel like mine," adapt as user clicks | Demo script + Query Guard with a fixed, explainable relaxation order |
| Going beyond minimum viable technique | MMR pass, bootstrap-validated weight selection, confidence-gated LLM stretch |
