"""
Connection helper for backend/app/*. Deliberately a near-duplicate of
backend/ingestion/db.py rather than a shared import across the two
directories — ingestion is a one-off offline job, the app is a long-lived
FastAPI process, and Block 5's eval harness needs to import from here
without dragging in the ingestion package. If this drifts out of sync
during the sprint, that's the tradeoff; revisit post-hackathon.
"""

from __future__ import annotations

import os

import psycopg2
import psycopg2.pool
from pgvector.psycopg2 import register_vector

_pool: psycopg2.pool.SimpleConnectionPool | None = None


def _connect_kwargs():
    return dict(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "wanderwise"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )


def init_pool(minconn: int = 1, maxconn: int = 10):
    """Call once, at FastAPI startup. A single Postgres instance (see
    ARCHITECTURE.md § 6) still benefits from a small pool instead of opening
    a new connection per request under load-testing or demo-day traffic."""
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.SimpleConnectionPool(minconn, maxconn, **_connect_kwargs())
    return _pool


def get_connection():
    """Borrow a connection from the pool, with pgvector adapters registered.

    Callers MUST return it with release_connection() (a `try/finally` or the
    `connection()` context manager below) — the pool is small enough that a
    few leaked connections will exhaust it mid-demo.
    """
    pool = init_pool()
    conn = pool.getconn()
    register_vector(conn)
    return conn


def release_connection(conn):
    if _pool is not None:
        _pool.putconn(conn)


class connection:
    """Context manager wrapper: `with connection() as conn: ...`"""

    def __enter__(self):
        self.conn = get_connection()
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        release_connection(self.conn)
