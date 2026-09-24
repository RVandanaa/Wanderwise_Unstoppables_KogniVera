# Evaluation — WanderWise

## Mandatory enhancement — Ablation Report (live, judge-facing)

This is a scored requirement, not an optional nice-to-have: **the same relevance metric must be
reported for two configurations on the same query set — retrieval only, and retrieval plus
personalised rerank — with the delta stated.** Credit is given specifically for the harness running
**live, in front of the judge**, against `eval_queries` and `eval_relevance_labels`, printing both
numbers and the difference on the spot — not for a delta computed once in Block 5 and shown as a
slide.

**What this means concretely:**
- A single command — `python eval/run_ablation.py` — runs both configurations back-to-back on the
  *same* query set (the 94 persona-linked `eval_queries`, per `§ Two distinct numbers` below, since
  a delta needs a profile on both sides) and prints:
  ```
  Config A — retrieval only:            NDCG@10 = 0.xxx   precision@10 = 0.xxx
  Config B — retrieval + rerank:        NDCG@10 = 0.xxx   precision@10 = 0.xxx
  Δ (B − A):                            NDCG@10 = +0.0xx  precision@10 = +0.0xx
  ```
- It must be fast enough to run **on demand**, live, while a judge is watching — not a batch job
  someone kicks off and waits three minutes for. Pre-warm the embedding model and DB connection
  before the demo slot (same warm-up discipline as the Meera query in `RISKS.md § 5`).
- The team states in plain language what the delta means — including if it's negative. **A negative
  delta with an honest explanation scores better than a single unexplained number.** If rerank
  underperforms retrieval-only on this query set, say so and say why (e.g. weight triple tuned on a
  20-query slice too small to generalise, or a popularity prior that's already doing most of the
  work) — see `EVALUATION.md § Weight selection` and `RISKS.md § 7` Tier 2 for the honesty-over-false-precision stance this design already takes elsewhere.
- This uses the same pipeline code as `/search` (`§ Harness implementation note` below) — the
  ablation script is not a separate reimplementation that could silently drift from what's deployed.

This requirement is what `PLAN.md` Block 6's rehearsal and the 15-second scripted aside in the demo
script are for — see `PLAN.md § Demo script inclusions`.

## Headline metric

**NDCG@10** is the primary reported number (labels in `eval_relevance_labels` are graded 0–3, which
NDCG uses natively); **precision@10** is reported alongside for readability.

Computed by running the actual retrieval+rerank pipeline — not a mock — against every `eval_queries`
row that targets `hotel`, `poi`, or `package` (all 120 do), scored against `eval_relevance_labels`.
Broken down by language and by intent, not one blended number.

### Two distinct numbers, not one

| Number | Queries | What it measures |
|---|---|---|
| Headline NDCG@10/precision@10 | All 120 `eval_queries` | Full pipeline end-to-end: retrieval + profile-aware rerank for the 94 carrying a `persona_user_id`, retrieval + popularity/rating prior only for the remaining 26 (no persona to personalise against) — exactly as a real anonymous/logged-out query would be served |
| Personalisation delta | 94 persona-linked `eval_queries` only | Rerank vs. a matched retrieval-only baseline, computed only where a profile exists on both sides of the comparison |

The 120-query number tells you how the system performs end-to-end; the 94-query number isolates what
the rerank step is buying.

## Scope of the graded set

- `eval_relevance_labels` only has grades for `hotel` (2,160), `poi` (960), and `package` (480) —
  the seven other `entity_type` values in the schema have no graded ground truth, so WanderWise
  scopes to these three types only.
- A fixed, disjoint 20-query slice of `eval_queries` is held out from the final reported metric and
  used only for weight-tuning (below), so the reported number is never tuned against itself.

## Retrieval-quality metric (pre-rerank)

Recall of the labelled-relevant set (grade ≥ 2) within the top-50 candidate pool, measured **before**
rerank runs — if relevant items aren't in the pool, no reranker can fix that. Reported per target
entity type.

## Weight selection (Section 8.2 methodology)

1. Grid-search a small set of weight triples — (query-sim, profile-sim, popularity-prior) — e.g.
   `{0.5, 0.3, 0.2}`, `{0.4, 0.4, 0.2}`, `{0.6, 0.2, 0.2}` — against the 20-query held-out slice.
2. Because 20 queries is a small sample, bootstrap-resample the held-out slice (200 resamples with
   replacement) for each weight triple.
3. Report the **median and interquartile range (IQR)** of NDCG@10 per triple, not a single point
   estimate — a triple that wins by a hair on one lucky ordering isn't mistaken for a real improvement.
4. Keep the triple with the best median NDCG@10; report its IQR alongside. If two triples' IQRs
   overlap heavily, state that explicitly rather than presenting false precision.
5. State the chosen weights, the slice they were tuned on, and the resampled spread plainly in the
   demo — "hand-tuned" means "tuned against a specific, named, held-out set, with the uncertainty
   shown," not "picked by feel."

## Diversity metric (MMR)

Intra-list diversity: average pairwise embedding-cosine-similarity within the top-10, computed
before vs. after the MMR pass, over the same 120 queries used for the headline metric. Reported
alongside NDCG@10 with the explicit caveat that MMR trades a small amount of top-1 relevance for
reduced redundancy. **If the trade-off measurably hurts NDCG beyond a small, named tolerance, MMR is
disabled for the demo** — the decision is made from the number, not asserted in advance.

## Cold-start (no direct metric)

No graded ground truth exists for cold-start personas (`persona_user_id` never resolves to a
`cold_start`-segment user in `eval_queries`), so cold start is demonstrated live (fresh session → two
clicks → visibly different ranking), not claimed as a number.

**Partial mitigation, time permitting**: for the 94 persona-linked queries that do have graded
labels, re-run the pipeline with that persona's `user_preferences`/`user_interactions` rows masked,
forcing the cold-start path, and compare NDCG@10 against the same queries' personalised score. This
isn't a cold-start ground-truth metric (the labels still assume a known persona), but it's a real,
gradeable check that the fallback degrades sensibly rather than collapsing.

## Explanation quality (not NDCG-measured)

A manual spot-check pass over a sample of explanations against their underlying score components
before the demo: is the stated reason actually the dominant one? This is the one feature in the
design that isn't measured by NDCG, and that's stated explicitly rather than force-fitting a metric
to it.

## Amenity-tag quality (not NDCG-measured)

Manual spot-check of extracted `hotel_amenity_tags` against source `hotels.description` for a random
~30-hotel sample, with `step_free_access` reviewed in full for every hotel surfacing in the demo
query (it's the exact filter used in the reference scenario in `PRD.md § 4`). Any tag that can't be
confirmed by eye is pulled rather than shipped.

## Soft-constraint extraction precision (stretch only)

Precision of extracted soft tags against a manually-labelled sample of 20 queries — does the tag
reflect what the traveller actually asked for? Checked before the demo, same spot-check discipline as
amenity tags, not a headline metric. The confidence-gate fallback rate is also logged during
smoke-testing — a feature that silently falls back on most real queries isn't worth demoing, and
that's stated if the number shows it.

## Stated targets (not pre-claimed results)

- Headline NDCG@10 measurably above the retrieval-only/popularity-prior baseline on the same 120
  queries, reported side by side rather than the delta alone.
- **Target**: a positive, double-digit-percent relative improvement in NDCG@10 on the 94
  persona-linked queries (rerank vs. retrieval-only baseline) — stated as a target we measure and
  report as-is, including if the real number comes in lower.

## Harness implementation note

The evaluation harness (`eval/run_harness.py`) runs the same pipeline code the API uses — not a
parallel implementation that could silently drift from what's deployed.
