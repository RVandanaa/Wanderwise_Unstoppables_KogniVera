"""
Block 0 scaffold — SQLite for local hello-world / early development.

Swap get_conn() for a psycopg2/asyncpg Postgres connection once Vandanaa's
Block 1 schema load (data/schema.sql into Postgres + pgvector) is done.
Everything downstream (retrieval.py, rerank.py) should only ever call
get_conn() — never import sqlite3 directly elsewhere — so that swap is
one function, not a grep-and-replace.
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "APS-04.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def healthcheck() -> dict:
    """Proves the DB file is real and queryable — not a mock."""
    with get_conn() as conn:
        cur = conn.cursor()
        counts = {}
        for table in ("hotels", "activities_poi", "tour_packages",
                      "eval_queries", "eval_relevance_labels", "user_interactions"):
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]
        return counts
