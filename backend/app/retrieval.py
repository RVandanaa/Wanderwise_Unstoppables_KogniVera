"""
retrieval.py — Block 2 (hours 4-8), owner: Prakruti.

Hybrid retrieval: embed the query (backend/app/query_embedder.py, same space
Block 1's embed_catalogue.py wrote item_embeddings into), then combine
pgvector cosine similarity with hard SQL filters parsed from `filters`
(ARCHITECTURE.md § 3 step 3).

Scope of this file, specifically: retrieval only. No rerank, no MMR, no
Query Guard relaxation/retry — those are Block 3 and Block 4. This returns
the top ~50 candidate pool by similarity within the hard filters, which is
exactly what the end-of-Block-2 checkpoint hand-validates against a few
`eval_queries` rows (PLAN.md go/no-go table) and what Block 5's
"retrieval-quality metric (pre-rerank)" measures recall over.

ASSUMPTIONS FLAGGED FOR VERIFICATION — same caveat as Block 1's
embed_catalogue.py: column names below are inferred from DATA_MODEL.md, not
read off the real schema.sql (not in this checkout when this was written).
Check ENTITY_CONFIG against the real schema before trusting this file's
output, especially:
  - the price expression per entity type (hotels definitely need the
    MIN(base_rate) subquery per DATA_MODEL.md; poi/package price column
    names are a guess — `entry_cost` for poi is named in DATA_MODEL.md, but
    tour_packages' price column is not, so `price` here is a placeholder)
  - whether `activities_poi`/`tour_packages` have a `category_id` FK to
    `categories`, and whether `filters.category` should match on
    `categories.code` (assumed) vs. some other column
  - whether hotels have any category at all — this file excludes hotels
    from a query that has `filters.category` set, on the assumption they
    don't (see `_applies_to` logic below)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from query_embedder import embed_query

# entity_type -> config describing how to build one candidate query.
# `supports` lists which filter keys this entity type has a column for;
# a filter present in the request but absent from `supports` excludes that
# entity type from the result set entirely, rather than silently ignoring
# the filter (a hotel result silently ignoring `category` would be a subtly
# wrong answer to a query that asked for one).
ENTITY_CONFIG: dict[str, dict[str, Any]] = {
    "hotel": {
        "table": "hotels h",
        "id_col": "h.hotel_id",
        "name_col": "h.name",
        "city_col": "h.city_id",
        "status_col": "h.status",
        "star_col": "h.star_rating",
        "category_col": None,
        # DATA_MODEL.md: hotels has no price column; the displayed "from"
        # price is MIN(base_rate) across that hotel's *active* room types.
        "price_expr": (
            "(SELECT MIN(rt.base_rate) FROM hotel_room_types rt "
            "WHERE rt.hotel_id = h.hotel_id AND rt.status = 'active')"
        ),
        "supports": {"city_id", "price_max", "star_min"},  # no category, no amenities (soft-only)
    },
    "poi": {
        "table": "activities_poi p",
        "id_col": "p.poi_id",
        "name_col": "p.name",
        "city_col": "p.city_id",
        "status_col": "p.status",
        "star_col": None,
        "category_col": "p.category_id",
        "price_expr": "p.entry_cost",
        "supports": {"city_id", "price_max", "category"},
    },
    "package": {
        "table": "tour_packages t",
        "id_col": "t.package_id",
        "name_col": "t.name",
        "city_col": "t.city_id",
        "status_col": "t.status",
        "star_col": None,
        "category_col": "t.category_id",
        "price_expr": "t.price",  # UNVERIFIED — see module docstring
        "supports": {"city_id", "price_max", "category"},
    },
}

DEFAULT_TOP_K = 50  # ARCHITECTURE.md § 3 step 4: candidate pool ~50


def _applies_to(entity_type: str, filters: dict) -> bool:
    """False if `filters` uses a key this entity type has no column for."""
    supports = ENTITY_CONFIG[entity_type]["supports"]
    for key, value in filters.items():
        if value in (None, [], ""):
            continue
        if key == "amenities":
            continue  # soft signal, never a hard filter — DATA_MODEL.md Rule R1
        if key not in supports:
            return False
    return True


def _build_query(entity_type: str, filters: dict) -> tuple[str, list]:
    cfg = ENTITY_CONFIG[entity_type]
    conditions = [f"{cfg['status_col']} = 'active'"]
    params: list = []

    if filters.get("city_id"):
        conditions.append(f"{cfg['city_col']} = %s")
        params.append(filters["city_id"])

    if filters.get("price_max") is not None:
        conditions.append(f"{cfg['price_expr']} IS NOT NULL AND {cfg['price_expr']} <= %s")
        params.append(Decimal(filters["price_max"]))

    if filters.get("star_min") is not None and cfg["star_col"]:
        conditions.append(f"{cfg['star_col']} >= %s")
        params.append(filters["star_min"])

    if filters.get("category") and cfg["category_col"]:
        conditions.append(
            f"{cfg['category_col']} = (SELECT category_id FROM categories WHERE code = %s)"
        )
        params.append(filters["category"])

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            '{entity_type}' AS entity_type,
            {cfg['id_col']} AS entity_id,
            {cfg['name_col']} AS name,
            1 - (ie.embedding <=> %s) AS similarity
        FROM {cfg['table']}
        JOIN item_embeddings ie
            ON ie.entity_type = '{entity_type}' AND ie.entity_id = {cfg['id_col']}
        WHERE {where_clause}
        ORDER BY ie.embedding <=> %s
        LIMIT %s
    """
    return query, params


def hybrid_retrieve(
    conn,
    query_text: str,
    filters: dict,
    top_k: int = DEFAULT_TOP_K,
    entity_types: list[str] | None = None,
) -> list[dict]:
    """Returns up to `top_k` candidates across the requested entity types,
    each a dict with entity_type, entity_id, name, similarity — sorted by
    similarity desc. `filters` is the raw `filters` dict from the request
    (already validated by Query Guard once Block 4 exists; this function
    does not itself validate — see module docstring).
    """
    query_vector = embed_query(query_text)
    entity_types = entity_types or list(ENTITY_CONFIG.keys())

    candidates: list[dict] = []
    with conn.cursor() as cur:
        for entity_type in entity_types:
            if not _applies_to(entity_type, filters):
                continue
            sql, params = _build_query(entity_type, filters)
            # query_vector appears twice: once in SELECT (similarity value),
            # once in ORDER BY (pgvector needs the operator repeated — it
            # doesn't reuse a computed column from SELECT in ORDER BY here
            # since we're not wrapping this in a subquery).
            full_params = [query_vector, *params, query_vector, top_k]
            cur.execute(sql, full_params)
            cols = [d.name for d in cur.description]
            candidates.extend(dict(zip(cols, row)) for row in cur.fetchall())

    candidates.sort(key=lambda c: c["similarity"], reverse=True)
    return candidates[:top_k]
