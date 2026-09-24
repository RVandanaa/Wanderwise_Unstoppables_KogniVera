"""
Query Guard — Prakruti's piece (ARCHITECTURE.md, RISKS.md § 6).

Block 0 status: filter validation against real enum/table values is
implemented and working today (needs only sqlite/Postgres + enums.json,
no embeddings). The post-retrieval pool-size check and relaxation retry
are stubbed — they need retrieval.py wired up first (Block 2).

Fixed relaxation priority (never changes, stated in the demo):
    star_min -> category -> price_max
city_id is NEVER auto-relaxed.
"""
import json
from pathlib import Path
from .db import get_conn

ENUMS_PATH = Path(__file__).resolve().parent.parent / "data" / "enums.json"
RELAXATION_ORDER = ["star_min", "category", "price_max"]


def _load_enums() -> dict:
    return json.loads(ENUMS_PATH.read_text())["enums"]


def validate_filters(filters: dict) -> list[str]:
    """Returns a list of validation error strings; empty list = valid.
    Checks numeric ranges and that city_id actually exists — real check
    against the real `cities` table, not a placeholder.
    """
    errors = []

    price_max = filters.get("price_max")
    if price_max is not None:
        try:
            val = float(price_max)  # display/validation only — real code must use Decimal, never float, for arithmetic (DATA_MODEL.md R3)
            if val <= 0:
                errors.append("price_max must be positive")
        except (TypeError, ValueError):
            errors.append(f"price_max is not a valid decimal string: {price_max!r}")

    star_min = filters.get("star_min")
    if star_min is not None and not (1 <= int(star_min) <= 5):
        errors.append("star_min must be between 1 and 5")

    city_id = filters.get("city_id")
    if city_id is not None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM cities WHERE city_id = ?", (city_id,)
            ).fetchone()
        if row is None:
            errors.append(f"unknown city_id: {city_id!r}")

    return errors


def check_pool_and_relax(candidate_count: int, filters: dict) -> dict:
    """
    STUB — wire this up in Block 4 once retrieval.py returns real candidate
    pools. Returns the query_guard response block shape from API_SPEC.md.
    """
    if candidate_count >= 10:
        return {"relaxed": False, "relaxed_filter": None,
                "narrow_results": False, "candidate_pool_size": candidate_count}
    if candidate_count >= 5:
        return {"relaxed": False, "relaxed_filter": None,
                "narrow_results": True, "candidate_pool_size": candidate_count}
    # TODO Block 4: actually relax the first present filter in RELAXATION_ORDER
    # and re-run retrieval once. This stub just reports what *would* relax.
    for f in RELAXATION_ORDER:
        if filters.get(f) is not None:
            return {"relaxed": True, "relaxed_filter": f,
                    "narrow_results": False, "candidate_pool_size": candidate_count}
    return {"relaxed": False, "relaxed_filter": None,
            "narrow_results": False, "candidate_pool_size": candidate_count}
