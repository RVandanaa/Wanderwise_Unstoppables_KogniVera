"""
Thin Postgres connection helper for the Block 1 ingestion scripts.

Reads connection settings from environment variables (see .env.example at the
repo root) rather than hardcoding them, since every teammate is running this
against their own local Postgres during the sprint.
"""

import os

import psycopg2
from pgvector.psycopg2 import register_vector


def get_connection():
    """Open a Postgres connection with the pgvector type adapter registered.

    Without register_vector(), psycopg2 has no idea how to adapt a numpy
    array / python list into the `vector` column type, and every insert
    into item_embeddings will fail with an adaptation error.
    """
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "wanderwise"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
    )
    register_vector(conn)
    return conn
