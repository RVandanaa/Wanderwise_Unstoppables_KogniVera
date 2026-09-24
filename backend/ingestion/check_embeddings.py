"""
check_embeddings.py — run right after embed_catalogue.py.

Not the official tools/validate_conformance.py (that's part of the given
data package and checks the raw dataset itself). This is a much smaller,
Block-1-specific sanity check: did the embedding job actually finish, for
every entity type, with no NULL vectors left behind?

Exits non-zero on any problem, so it can be chained:
    python backend/ingestion/embed_catalogue.py && \
    python backend/ingestion/check_embeddings.py
"""

import sys

from db import get_connection


def main():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT entity_type, count(*), count(*) FILTER (WHERE embedding IS NULL)
                FROM item_embeddings
                GROUP BY entity_type
                ORDER BY entity_type
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("FAIL: item_embeddings is empty — did embed_catalogue.py run?")
        sys.exit(1)

    ok = True
    print(f"{'entity_type':<10} {'rows':>8} {'null_embeddings':>16}")
    for entity_type, total, nulls in rows:
        flag = "" if nulls == 0 else "  <-- FAIL"
        print(f"{entity_type:<10} {total:>8} {nulls:>16}{flag}")
        if nulls > 0:
            ok = False

    expected = {"hotel", "poi", "package"}
    present = {r[0] for r in rows}
    missing = expected - present
    if missing:
        print(f"FAIL: no rows at all for entity type(s): {sorted(missing)}")
        ok = False

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
