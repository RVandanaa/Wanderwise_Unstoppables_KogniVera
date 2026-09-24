"""
embed_catalogue.py — Block 1 (hours 0-4), owner: Vandanaa.

Embeds the `description` text of every active row in hotels, activities_poi,
and tour_packages using the shared multilingual sentence-transformer
(paraphrase-multilingual-MiniLM-L12-v2, see ARCHITECTURE.md), and upserts the
result into `item_embeddings` (data/migrations/001_item_embeddings.sql).

Run order (README.md "Running locally"):
    1. psql -d wanderwise -f data/schema.sql
    2. load data/csv/*.csv in numbered order
    3. psql -d wanderwise -f data/migrations/001_item_embeddings.sql
    4. python3 tools/validate_conformance.py data/APS-04.db   <- run this first
    5. python backend/ingestion/embed_catalogue.py            <- this script

IMPORTANT — verify before running:
    The table/column names below (TABLE_CONFIG) are this script's assumption
    of what the given schema.sql calls things, based on DATA_MODEL.md's
    description of each table. The actual data package wasn't in this repo
    checkout when this script was written. Before Block 1 starts for real,
    diff TABLE_CONFIG against the real `data/schema.sql` and fix any mismatch
    — a wrong column name fails loudly (psycopg2 UndefinedColumn), a wrong
    *table* name that happens to half-match something else would not.

Idempotent by design: each row's description is hashed (md5), and a row is
only re-embedded if its hash has changed since the last run — so re-running
this after a partial failure, or after new CSV rows land, doesn't cost a
full re-embed of the catalogue.
"""

import argparse
import hashlib
import logging
import sys
import time

from db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("embed_catalogue")

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384  # must match data/migrations/001_item_embeddings.sql

# entity_type -> (source table, id column, description column, status column)
# Rule R8 (DATA_MODEL.md): nothing is hard-deleted, so every read filters
# status = 'active' explicitly rather than assuming absence means removed.
TABLE_CONFIG = {
    "hotel": {
        "table": "hotels",
        "id_col": "hotel_id",
        "description_col": "description",
        "status_col": "status",
    },
    "poi": {
        "table": "activities_poi",
        "id_col": "poi_id",
        "description_col": "description",
        "status_col": "status",
    },
    "package": {
        "table": "tour_packages",
        "id_col": "package_id",
        "description_col": "description",
        "status_col": "status",
    },
}


def hash_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def fetch_rows(conn, entity_type: str):
    """Fetch (id, description) for every active row of one catalogue table."""
    cfg = TABLE_CONFIG[entity_type]
    query = (
        f"SELECT {cfg['id_col']}, {cfg['description_col']} "
        f"FROM {cfg['table']} "
        f"WHERE {cfg['status_col']} = 'active'"
    )
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def fetch_existing_hashes(conn, entity_type: str) -> dict:
    """entity_id -> source_hash already stored, so unchanged rows are skipped."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT entity_id, source_hash FROM item_embeddings WHERE entity_type = %s",
            (entity_type,),
        )
        return dict(cur.fetchall())


def upsert_embeddings(conn, entity_type: str, rows: list):
    """rows: list of (entity_id, embedding, source_hash)."""
    if not rows:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO item_embeddings (entity_type, entity_id, embedding, source_hash, updated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (entity_type, entity_id)
            DO UPDATE SET
                embedding = EXCLUDED.embedding,
                source_hash = EXCLUDED.source_hash,
                updated_at = now()
            """,
            [(entity_type, entity_id, embedding, source_hash) for entity_id, embedding, source_hash in rows],
        )
    conn.commit()


def embed_entity_type(model, conn, entity_type: str, batch_size: int, force: bool) -> tuple[int, int]:
    """Returns (embedded_count, skipped_unchanged_count)."""
    rows = fetch_rows(conn, entity_type)
    existing_hashes = {} if force else fetch_existing_hashes(conn, entity_type)

    to_embed = []  # (entity_id, description, source_hash)
    skipped = 0
    for entity_id, description in rows:
        if not description or not description.strip():
            log.warning("  %s %s has an empty description — skipping, not embedding blank text", entity_type, entity_id)
            continue
        digest = hash_text(description)
        if existing_hashes.get(entity_id) == digest:
            skipped += 1
            continue
        to_embed.append((entity_id, description, digest))

    if not to_embed:
        log.info("  %s: nothing to embed (%d unchanged, skipped)", entity_type, skipped)
        return 0, skipped

    log.info("  %s: embedding %d rows (%d unchanged, skipped)", entity_type, len(to_embed), skipped)

    embedded_total = 0
    for start in range(0, len(to_embed), batch_size):
        batch = to_embed[start : start + batch_size]
        texts = [description for _, description, _ in batch]
        vectors = model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)

        upsert_rows = [
            (entity_id, vector, digest)
            for (entity_id, _description, digest), vector in zip(batch, vectors)
        ]
        upsert_embeddings(conn, entity_type, upsert_rows)
        embedded_total += len(upsert_rows)
        log.info("    ...%d/%d", embedded_total, len(to_embed))

    return embedded_total, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entity-types",
        default="hotel,poi,package",
        help="Comma-separated subset of {hotel,poi,package} to run (default: all three)",
    )
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed every row regardless of source_hash (use after a model change)",
    )
    args = parser.parse_args()

    entity_types = [e.strip() for e in args.entity_types.split(",") if e.strip()]
    for e in entity_types:
        if e not in TABLE_CONFIG:
            parser.error(f"Unknown entity type '{e}' — must be one of {list(TABLE_CONFIG)}")

    # Imported here, not at module scope, so `--help` doesn't pay the model
    # library's import cost.
    from sentence_transformers import SentenceTransformer

    log.info("Loading %s ...", MODEL_NAME)
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    if model.get_sentence_embedding_dimension() != EMBEDDING_DIM:
        log.error(
            "Model dim %d != EMBEDDING_DIM %d — update EMBEDDING_DIM here and "
            "the vector(%d) column in 001_item_embeddings.sql together",
            model.get_sentence_embedding_dimension(),
            EMBEDDING_DIM,
            EMBEDDING_DIM,
        )
        sys.exit(1)
    log.info("Model loaded in %.1fs", time.time() - t0)

    conn = get_connection()
    try:
        totals = {}
        for entity_type in entity_types:
            log.info("Entity type: %s", entity_type)
            embedded, skipped = embed_entity_type(model, conn, entity_type, args.batch_size, args.force)
            totals[entity_type] = (embedded, skipped)
    finally:
        conn.close()

    log.info("Done.")
    for entity_type, (embedded, skipped) in totals.items():
        log.info("  %-8s embedded=%-5d unchanged_skipped=%d", entity_type, embedded, skipped)


if __name__ == "__main__":
    main()
