"""
Personalised Reranker — Prakruti's piece (EVALUATION.md § Weight selection).

Block 0 status: STUB. Returns candidates in their incoming (query-similarity)
order with a passthrough score. Block 3 replaces `score()` with the real
blend: w1*query_sim + w2*profile_sim + w3*popularity_prior, with
w1/w2/w3 chosen by the grid search + bootstrap procedure in EVALUATION.md.
The MMR diversity pass (§8.7) is a second stage added after that, inside
this same module, not a separate service.
"""

# Placeholder weights — DO NOT treat as final. Real values come from the
# Block 3 grid search over {0.5,0.3,0.2} / {0.4,0.4,0.2} / {0.6,0.2,0.2}
# against the 20-query held-out slice (EVALUATION.md).
WEIGHTS = {"query_sim": 1.0, "profile_sim": 0.0, "popularity_prior": 0.0}


def score(candidate: dict, profile_sim: float = 0.0, popularity_prior: float = 0.0) -> float:
    return (
        WEIGHTS["query_sim"] * candidate["query_similarity"]
        + WEIGHTS["profile_sim"] * profile_sim
        + WEIGHTS["popularity_prior"] * popularity_prior
    )


def rerank(candidates: list[dict], user_profile: dict | None = None) -> list[dict]:
    """STUB: no profile signal or MMR yet — passthrough scoring only."""
    for c in candidates:
        c["score"] = score(c)
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates
