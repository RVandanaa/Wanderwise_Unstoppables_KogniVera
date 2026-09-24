"""
Hybrid Retrieval — Prakruti's piece (ARCHITECTURE.md § 2, PLAN.md Block 2).

Block 0 status:
  - SQL-filter half (city_id, price_max, star_min) is REAL and working
    against the actual APS-04.db hotels/hotel_room_types tables.
  - Vector-similarity half is STUBBED (returns a constant similarity)
    until Vandanaa's embedding job (Block 1) populates item_embeddings
    and this environment has network access to the embedding model.
    Swap `_stub_query_similarity` for a real pgvector `<=>` query once
    that's ready — the SQL-filter query below does not need to change.

Money handling: base_rate is a TEXT decimal string in the DB (DATA_MODEL.md
R3). We compare using Decimal, never float, even though this is "just" a
filter — the eight rules apply to every field that came with the dataset.
"""
from decimal import Decimal
from .db import get_conn


def _stub_query_similarity(item_id: str, query_text: str) -> float:
    # TODO Block 2/3: replace with real cosine similarity against
    # item_embeddings once populated. Constant for now so the pipeline
    # is wireable end-to-end today.
    return 0.5


def hybrid_retrieve(query_text: str, filters: dict, limit: int = 50) -> list[dict]:
    """
    Returns candidate hotels matching the hard SQL filters, each tagged
    with a (currently stubbed) query-similarity score. `hotels` has no
    price column — price is the MIN(base_rate) across a hotel's active
    room types, computed here at query time (DATA_MODEL.md).
    """
    clauses = ["h.status = 'active'"]
    params: list = []

    if filters.get("city_id"):
        clauses.append("h.city_id = ?")
        params.append(filters["city_id"])

    if filters.get("star_min") is not None:
        clauses.append("h.star_rating >= ?")
        params.append(int(filters["star_min"]))

    where_sql = " AND ".join(clauses)

    sql = f"""
        SELECT h.hotel_id, h.name, h.city_id, h.star_rating, h.guest_score,
               h.description,
               (SELECT MIN(CAST(rt.base_rate AS REAL))
                FROM hotel_room_types rt
                WHERE rt.hotel_id = h.hotel_id AND rt.status = 'active') AS from_price
        FROM hotels h
        WHERE {where_sql}
    """

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    price_max = filters.get("price_max")
    price_max_dec = Decimal(str(price_max)) if price_max is not None else None

    results = []
    for r in rows:
        if r["from_price"] is None:
            continue
        from_price_dec = Decimal(str(r["from_price"]))
        if price_max_dec is not None and from_price_dec > price_max_dec:
            continue
        results.append({
            "entity_type": "hotel",
            "entity_id": r["hotel_id"],
            "name": r["name"],
            "city_id": r["city_id"],
            "star_rating": r["star_rating"],
            "guest_score": r["guest_score"],
            "from_price": str(from_price_dec),
            "query_similarity": _stub_query_similarity(r["hotel_id"], query_text),
        })

    results.sort(key=lambda x: x["query_similarity"], reverse=True)
    return results[:limit]
