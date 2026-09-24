# 24-Hour Plan — WanderWise

## Before the sprint — from the official `04_HACKATHON_DAY_PROCESS`

Sprint window: **24 September 12:00 → 25 September 12:00** (12:00-to-12:00, exactly — a commit at
12:01 on the 25th is a commit after the sprint). Presentations post-lunch on the 25th; finale on the 26th.

**One week out** (should already be done):
- [ ] Every member can build and run the project from a clean checkout
- [ ] Accounts, API keys and quotas obtained and *tested* — not just requested
- [ ] The provided dataset loaded and queried by at least two people on the team
- [ ] `tools/validate_conformance.py` run once, and it passes
- [ ] Decided who does what, and who owns the demo (matches the ownership table above)

**The day before**:
- [ ] Repository created, everyone has push access, everyone has cloned it
- [ ] Dependencies installed on every machine — do not plan to install over venue wi-fi
- [ ] A hello-world deploy of the stack running end to end
- [ ] Laptops, chargers, adapters, a power strip, a spare mouse
- [ ] Sleep — teams that demo badly are usually the ones that didn't

**First hour of the sprint (12:00–13:00, 24 Sep) — not writing code**: agree the single flow to demo
(the Meera/Udaipur scenario in `PRD.md § 4`), confirm who owns which piece (table below), and what
gets cut first if behind schedule (`RISKS.md § 7` tiered cut list). Teams that skip this hour lose
four later.

**09:00, 25 September — the 09:00 rule**: three hours left, stop building features entirely.
09:00–11:00 stabilise and fix the demo path only, nothing new. 11:00–12:00 rehearse the demo twice
on the actual machine it'll be presented from. 12:00 is a hard stop — submission closes.

**What's due at 12:00 on the 25th**: running application/demo covering the MVP scope, a short
solution write-up, the final presentation, and the source repository + a brief architecture note
(`ARCHITECTURE.md` in this repo covers the latter).

**Presentation format** (post-lunch, 25th): show the thing running in the first two minutes — no
slides before the demo. Demo the one rehearsed flow end to end. Show the AI feature working live, on
real data, not a screenshot. State what was cut and why (deliberate scope reads as judgement — see
`PRD.md § Deliberately not building`). Have an offline recorded fallback run ready in case venue
wi-fi fails. Decide in advance who speaks — two voices maximum.

## Block schedule

| Block | Hours | Focus | Owner |
|---|---|---|---|
| 1 | 0–4 | Postgres schema loaded from `data/schema.sql` + CSVs; embedding job run over `hotels`/`activities_poi`/`tour_packages` descriptions; `item_embeddings` populated; conformance check passing. Pranav starts frontend against a mocked API response so frontend never blocks on backend status. Vandanaa cross-trains on rerank/cold-start logic with Prakruti while the embedding job runs unattended (Risk 4 mitigation). | Vandanaa (schema + embedding job, cross-training), Prakruti (conformance check, cross-training), Pranav (frontend scaffold against mocks) |
| 2 | 4–8 | Hybrid retrieval endpoint: pgvector similarity + SQL filters from `filters_json`; validated by hand against a few `eval_queries` rows. | Prakruti |
| 3 | 8–12 | Rerank + weight grid search against the held-out 20-query slice + explanation templates + MMR diversity pass; cold-start fallback (given to Vandanaa, see Risk 4); amenity tag extraction job with negation check + spot-check. **End of block: smoke-test the full pipeline against ~10 `eval_queries` by hand**, including a per-stage latency log against the Section 5 budget. | Prakruti (rerank, weight search, explanations, MMR), Vandanaa (cold-start fallback, amenity extraction + spot-check + latency logging), all three on smoke test |
| 4 | 12–16 | Session profile store + in-session rerank loop; Query Guard (filter validation, fixed relaxation order, empty-pool retry, borderline-pool flag); frontend result list + filter chips + explanation line, wired to the real API. Query Guard's filter-validation half is pair-built with Pranav, since he already owns the `filters_json` shape. | Prakruti (session store, Query Guard core), Pranav (frontend result list, filter chips, explanation line, Query Guard filter-validation pairing) |
| 5 | 16–20 | Evaluation harness: run all 120 `eval_queries` through the live pipeline, compute NDCG@10/precision@10, break down by language and intent; retrieval-only baseline for comparison; intra-list diversity metric before/after MMR; bootstrap-resampled weight-selection report. **Go/no-go for the LLM soft-constraint stretch made at hour 18** — built only if the harness core is clean and at least 2 hours of slack remain before Block 6; otherwise explicitly deferred. | Vandanaa (harness build + run), Prakruti (pipeline support if the run surfaces a bug — cross-trained Vandanaa can take this if Prakruti is blocked) |
| 6 | 20–24 | Bug fixes against whatever the metric run exposes; multilingual demo script (`hi`, `ta` queries); cold-start live-demo script; LLM soft-constraint stretch only if greenlit at hour 18. **Stop building by hour 22; rehearse for the last 2 hours.** | Prakruti + Vandanaa (bug fixes), Pranav (demo scripts + screen flow), all three rehearse from hour 22 |

## Go/no-go checkpoints

| Checkpoint | Condition | If it fails |
|---|---|---|
| End of Block 2 | Hybrid retrieval returns correct results for 5 hand-checked `eval_queries` | Block 3's time budget shrinks to protect Block 4/5 |
| End of Block 3 | Smoke test (10 queries, full pipeline, latency logged) passes | MMR — newest, least load-bearing piece — is the first thing cut |
| Hour 18 | Harness core clean + ≥2 hours slack before Block 6 | LLM soft-constraint stretch deferred, not built cold in Block 6 |
| Hour 22 | Building stops regardless of what's incomplete | Anything unfinished is cut from the demo script or shown as a known limitation — never a live gamble |

## Mandatory demo moment — live ablation run

Distinct from the rest of the demo script and not optional: at some point in the slot, run
`python eval/run_ablation.py` live, on the presenting machine, and let it print the two NDCG@10/
precision@10 numbers and the delta on screen while the judge watches. Rehearse this specifically
during the 11:00–12:00 rehearsal window on the 25th (see checklist above), including:
- Pre-warming the embedding model and DB connection before the slot so the command returns in a
  demo-appropriate few seconds, not a visible pause.
- A rehearsed, ≤20-second explanation of what the delta means — said out loud regardless of whether
  it's positive or negative. See `EVALUATION.md § Mandatory enhancement` for the honesty stance if
  the number comes in lower than hoped.
- A tested fallback: if the live DB or embedding model is somehow unavailable on stage, a cached
  JSON of the last successful ablation run, clearly labelled as a fallback if it has to be used —
  the live run is what's rehearsed and expected, this is only for a true on-stage outage.

## Demo script inclusions (from rehearsal, hour 22–24)

The demo script includes, verbatim, a 15-second aside on:
- the bootstrap confidence interval on weight selection (`EVALUATION.md`), and
- the cold-start refusal to claim a fabricated metric (`PRD.md § Deliberately not building`, `RISKS.md § 3`).

These are the two differentiators most likely to go unmentioned if left implicit — they are the last
thing cut from the script if rehearsal runs short, never the first.
