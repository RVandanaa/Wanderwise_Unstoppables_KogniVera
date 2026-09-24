"""
Explanation Generator — Prakruti's piece (EVALUATION.md § Explanation quality).

Block 0 status: STUB covering the one signal that's real today (price
filter match). Block 3 extends this to template-fill from whichever score
component actually dominated (profile match, liked-item similarity, etc.)
per candidate — never an LLM asked to improvise a reason.
"""


def explain(candidate: dict, filters: dict) -> str:
    price_max = filters.get("price_max")
    if price_max is not None:
        return f"within your \u20b9{price_max} budget"
    if filters.get("star_min") is not None:
        return f"matches your {filters['star_min']}\u2605+ request"
    return "popular with travellers like you"
