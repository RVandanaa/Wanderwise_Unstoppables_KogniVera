# Risks & Fallbacks — WanderWise

## 1. Multilingual embedding quality is uneven across languages

`hi` (1,252 reviews, 16 eval queries) and `ta` (752 reviews, 16 eval queries) are the best-supported
non-English languages; `ml` (539 reviews, 8 eval queries) is thinner.

**Fallback**: demo confidently in `hi` and `ta`; report the NDCG breakdown honestly per language
rather than hiding a weak number; treat `ml` as a stretch, not a committed claim.

## 2. The amenity signal is inferred, not structured

Keyword extraction on free-text `description` will misclassify some hotels — most likely a false
positive from negated text ("no pool", "not wheelchair accessible" tagged as if present).

**Fallback**: extraction checks a ±5-token window around each matched keyword for a negation term
(`no`, `not`, `without`, `lacks`) and drops the tag when negation is found. Amenities remain a soft
rerank boost, never a hard filter, so a bad tag downgrades a ranking rather than silently dropping a
relevant hotel entirely. Manual spot-check over a random ~30-hotel sample during Block 3, with
`step_free_access` reviewed in full for every hotel that surfaces in the demo query. Any unconfirmed
tag is pulled rather than shipped.

## 3. Cold start has no graded ground truth to score against

**Fallback**: a scripted, honest live demo (fresh session → two clicks → visibly different ranking)
instead of a fabricated metric — stated plainly on the day as demonstrated, not measured.

**Partial mitigation, time permitting** (Block 5, after the headline metric run): re-run the 94
persona-linked queries with that persona's preference/interaction rows masked, forcing the cold-start
path, and compare NDCG@10 against the personalised score. First thing cut if Block 5 is tight, since
the live demo already covers the qualitative case.

## 4. Backend/AI ownership was originally concentrated in one person

Deliberately cut down rather than mitigated around: cold-start fallback (the simplest of the five
backend pieces — a straight preferences + popularity-prior lookup) is owned by Vandanaa from Block 3
onward, leaving Prakruti four interdependent pieces (retrieval, rerank+MMR, session store, Query
Guard) instead of five.

**Remaining fallback**: Vandanaa cross-trains on rerank logic during Block 1 while her embedding job
runs unattended, so she can take over rerank debugging if Prakruti is blocked. Pranav's frontend work
is decoupled from backend status from hour 0 (built against a mocked API response) until Block 4.
Block 4 (Query Guard + session store) is paired with Pranav on the filter-validation half, since he
already owns the `filters_json` shape from the frontend side.

**Checked, not assumed**: at the hour-8 checkpoint, Vandanaa independently re-derives the rerank
formula from memory before Block 3 begins; if she can't, remaining Block 1 slack goes to
re-explaining it rather than discovering the gap mid-Block-3.

## 5. Four sequential stages per request risk a visible on-stage stall

Query Guard → retrieval → rerank+MMR → explanation.

**Fallback**: a per-stage latency budget (retrieval < 300ms, rerank+MMR < 100ms, explanation < 50ms,
end-to-end < 600ms) set and logged during the Block 3 smoke test, not assumed. The exact demo query
is pre-run before going on stage so the first click is warm. If any stage exceeds budget during
Block 3, the first lever is cutting candidate-pool size (top-50 → top-20).

## 6. A pool of 5–9 candidates technically clears the Query Guard relaxation trigger but is still thin

Presenting it identically to a normal 20+ result pool would be quietly misleading.

**Fallback**: a distinct `narrow_results: true` flag surfaces a one-line notice on the frontend
rather than silently presenting a short list as a full one — one boolean, one UI string, cheap
because it was named as a gap during design.

## 7. Block 5 (the evaluation harness) is the largest single block and most likely to run long

**Fallback — tiered cut list, ordered to remove rigor before coverage**, applied if Block 5 is still
running past hour 18:

| Tier | Cut | Savings |
|---|---|---|
| 1 (already named at end of Block 3) | MMR diversity pass cut first — smallest, newest, least load-bearing piece | — |
| 2 | Bootstrap resampling on weight selection dropped for a single grid-search pass without the 200-resample CI; report the point estimate and state plainly that stability wasn't verified | ~45–60 min of harness-code time |
| 3 | Per-language NDCG breakdown deferred — report one blended headline number, compute the per-language split post-demo if time allows | — |
| Unaffected | LLM soft-constraint stretch — already deferred independently via its own hour-18 checkpoint | — |

A working system with a thinner evaluation story beats a broken demo with a beautiful one — this
order is decided in advance rather than under pressure at hour 19.

## 8. The mandatory ablation report must run live, in front of the judge — not just exist as a number

This is a scored requirement (`EVALUATION.md § Mandatory enhancement`), which raises the stakes on a
live demo moment beyond the rest of the presentation: a stall or crash here isn't just an awkward
pause, it's visibly failing to show the one thing this hackathon statement is graded on.

**Fallback**: pre-warm the embedding model and DB connection before the demo slot, same discipline
as the Meera query warm-up (Risk 5). Keep `eval/run_ablation.py` scoped to the 94-query
persona-linked subset, not all 120 — smaller, faster, and it's the set the delta is actually
meaningful on. Cache the last successful run's output as JSON so a true on-stage outage (venue
wi-fi, a dead DB connection) has a clearly-labelled fallback to show instead of nothing — but this is
a last resort, not the plan: the live run is what's rehearsed, and what's rehearsed is what the 25th
morning's 11:00–12:00 slot (`PLAN.md`) is for.

**If the delta comes in negative**: say so, plainly, with a one-sentence reason (e.g. the grid-search
weight triple was tuned on a 20-query slice too small to generalise, or the popularity prior was
already capturing most of the signal on this query mix). `EVALUATION.md` and this design's own stated
philosophy throughout (`RISKS.md § 3`, Tier 2 above) is that an honest negative result scores better
than an unexplained or quietly-hidden one — this is the one place in the whole submission where that
principle is explicitly graded, not just good practice.
