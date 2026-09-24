"""
cold_start.py — Block 3 (hours 8-12), owner: Vandanaa (RISKS.md § 4: "the
simplest of the five backend pieces — a straight preferences +
popularity-prior lookup").

Scope: score a retrieval candidate pool for a user who has no interaction
history to personalise against — either a `cold_start`-segment user (has
`user_preferences`, no meaningful `user_interactions`) or a fully anonymous
session (no `user_id` at all). ARCHITECTURE.md's Personalised Reranker
handles the normal (has-history) case; this module is what it calls instead
for the cold-start case, per the same section: "For zero-interaction users:
`user_preferences` + popularity/rating prior only."

This does NOT do MMR, does NOT read `user_interactions`, and does NOT
compute the grid-searched blend weights Prakruti's rerank.py uses for
regular users — those weights are tuned against graded ground truth
(EVALUATION.md § Weight selection), and no graded ground truth exists for
cold-start personas (EVALUATION.md § Cold-start). The weights below
(`W_QUERY_SIM`, `W_POPULARITY`, `W_PREFERENCE`) are a plain heuristic split,
not a tuned result — stated as such on demo day (RISKS.md § 3), not
presented as measured.

Integration point for Prakruti (Block 4): call `score_candidates()` with the
retrieval pool (from `retrieval.hybrid_retrieve`) plus the user's
`user_preferences` row (or `None` for anonymous). It returns the same
candidate dicts with a `score` and `explanation` field added, sorted
descending — a drop-in replacement for whatever the normal rerank step
would have produced, at the same seam in the pipeline.

ASSUMPTIONS FLAGGED — same caveat as the rest of this repo: popularity-prior
column names are inferred from DATA_MODEL.md ("hotels.guest_score",
"activities_poi.value_score"); tour_packages' equivalent is a guess
(`t.rating`) since DATA_MODEL.md doesn't name one — verify and fix
POPULARITY_CONFIG before trusting package scores.
"""

from __future__ import annotations

W_QUERY_SIM = 0.5
W_POPULARITY = 0.3
W_PREFERENCE = 0.2

# entity_type -> (table alias config for a popularity/rating column, its
# assumed scale, used to normalize onto 0-1 before blending).
POPULARITY_CONFIG = {
    "hotel": {"column": "guest_score", "max_value": 10.0},
    "poi": {"column": "value_score", "max_value": 10.0},
    "package": {"column": "rating", "max_value": 5.0},  # UNVERIFIED — see module docstring
}


def fetch_popularity_scores(conn, candidates: list[dict]) -> dict[tuple[str, str], float]:
    """Returns {(entity_type, entity_id): normalized_popularity_0_to_1}.

    One query per entity type present in `candidates`, not one row at a
    time — the candidate pool is already small (~50) so this is a handful
    of queries, not N.
    """
    by_type: dict[str, list[str]] = {}
    for c in candidates:
        by_type.setdefault(c["entity_type"], []).append(c["entity_id"])

    table_for_type = {"hotel": "hotels", "poi": "activities_poi", "package": "tour_packages"}
    id_col_for_type = {"hotel": "hotel_id", "poi": "poi_id", "package": "package_id"}

    scores: dict[tuple[str, str], float] = {}
    with conn.cursor() as cur:
        for entity_type, ids in by_type.items():
            cfg = POPULARITY_CONFIG[entity_type]
            table = table_for_type[entity_type]
            id_col = id_col_for_type[entity_type]
            cur.execute(
                f"SELECT {id_col}, {cfg['column']} FROM {table} WHERE {id_col} = ANY(%s)",
                (ids,),
            )
            for entity_id, raw_value in cur.fetchall():
                normalized = 0.0 if raw_value is None else max(0.0, min(1.0, float(raw_value) / cfg["max_value"]))
                scores[(entity_type, entity_id)] = normalized

    return scores


def preference_match_bonus(entity_type: str, category: str | None, price, user_preferences: dict | None) -> tuple[float, str | None]:
    """Returns (bonus in [0, 1], reason string or None). No user_preferences
    (fully anonymous session, API_SPEC.md notes) means this is always
    (0.0, None) — popularity alone drives the score, matching
    ARCHITECTURE.md's "no preferences for a fully anonymous session" case.
    """
    if user_preferences is None:
        return 0.0, None

    points = 0.0
    reasons = []

    interests = user_preferences.get("interests") or []
    if category and category in interests:
        points += 0.6
        reasons.append(f"matches your interest in {category}")

    max_daily_budget = user_preferences.get("max_daily_budget")
    if max_daily_budget is not None and price is not None:
        try:
            if float(price) <= float(max_daily_budget):
                points += 0.4
                reasons.append("within your usual budget")
        except (TypeError, ValueError):
            pass  # price/budget not comparable (missing price, bad data) — skip the bonus, don't crash the request

    return min(points, 1.0), (reasons[0] if reasons else None)


def score_candidates(conn, candidates: list[dict], user_preferences: dict | None) -> list[dict]:
    """candidates: output of retrieval.hybrid_retrieve() — each dict has at
    least entity_type, entity_id, name, similarity, and ideally `category`
    and `price` if the caller has them (retrieval.py's current Block 2
    output doesn't select those columns yet — Block 4 wiring should extend
    the retrieval SELECT or fetch them here; falling back to None is safe
    but means the preference-match bonus can't fire on category/price for
    candidates missing that data).

    Returns the same candidates with `score` (float) and `explanation`
    (str) added, sorted by score descending.
    """
    popularity = fetch_popularity_scores(conn, candidates)

    scored = []
    for c in candidates:
        pop = popularity.get((c["entity_type"], c["entity_id"]), 0.0)
        pref_bonus, pref_reason = preference_match_bonus(
            c["entity_type"], c.get("category"), c.get("price"), user_preferences
        )

        score = W_QUERY_SIM * c["similarity"] + W_POPULARITY * pop + W_PREFERENCE * pref_bonus

        # Explanation: name whichever component actually dominated this
        # item's score, not a generic line — matches explain.py's stated
        # approach (ARCHITECTURE.md) even though explain.py itself is
        # Block 3/Prakruti's file; this local version exists so a
        # cold-start-scored candidate isn't left without any explanation
        # if this module is used standalone before explain.py is wired in.
        components = {
            "similarity to your search": W_QUERY_SIM * c["similarity"],
            "popular with other travellers": W_POPULARITY * pop,
        }
        if pref_reason:
            components[pref_reason] = W_PREFERENCE * pref_bonus
        explanation = max(components, key=components.get)

        scored.append({**c, "score": round(score, 4), "explanation": explanation})

    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored
