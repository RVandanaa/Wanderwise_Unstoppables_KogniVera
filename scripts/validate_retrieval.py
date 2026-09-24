"""
validate_retrieval.py — supports the Block 2 go/no-go checkpoint
(PLAN.md: "Hybrid retrieval returns correct results for 5 hand-checked
eval_queries").

Not an automated pass/fail — the checkpoint is explicitly "hand-checked".
This script pulls N eval_queries rows, runs them through hybrid_retrieve,
and prints the candidate pool next to that query's grade-3 (best) labels
from eval_relevance_labels, so a person can eyeball whether the pool looks
right. It also prints a rough recall number (grade >= 2 labels found
anywhere in the pool) as a sanity signal — not the real, precise Block 5
retrieval-quality metric (EVALUATION.md), which is computed properly over
all 120 queries by the harness, not this script.

ASSUMPTIONS FLAGGED — eval_queries/eval_relevance_labels column names below
are inferred (query_id, query_text, language, filters_json, persona_user_id
/ target_entity_type; grade, entity_type, entity_id) since the real
schema.sql wasn't available when this was written. Fix the SQL below if the
real column names differ.

Usage:
    python scripts/validate_retrieval.py --n 5
    python scripts/validate_retrieval.py --query-id evq_00042
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "app"))

import db  # noqa: E402
from retrieval import DEFAULT_TOP_K, hybrid_retrieve  # noqa: E402


def fetch_queries(conn, n: int, query_id: str | None):
    with conn.cursor() as cur:
        if query_id:
            cur.execute(
                "SELECT query_id, query_text, language, filters_json FROM eval_queries WHERE query_id = %s",
                (query_id,),
            )
        else:
            cur.execute(
                "SELECT query_id, query_text, language, filters_json FROM eval_queries ORDER BY random() LIMIT %s",
                (n,),
            )
        return cur.fetchall()


def fetch_relevant_labels(conn, query_id: str):
    """grade >= 2 labels for this query — the "should be in the top-50" set."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT entity_type, entity_id, grade FROM eval_relevance_labels "
            "WHERE query_id = %s AND grade >= 2 ORDER BY grade DESC",
            (query_id,),
        )
        return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=5, help="number of random eval_queries rows to check")
    parser.add_argument("--query-id", default=None, help="check one specific query instead of a random sample")
    args = parser.parse_args()

    with db.connection() as conn:
        queries = fetch_queries(conn, args.n, args.query_id)
        if not queries:
            print("No eval_queries rows found — check the table name/filter above.")
            return

        hit_count = 0
        label_count = 0

        for query_id, query_text, language, filters_json in queries:
            filters = filters_json if isinstance(filters_json, dict) else json.loads(filters_json or "{}")

            print("=" * 80)
            print(f"{query_id}  [{language}]  {query_text!r}")
            print(f"  filters: {filters}")

            candidates = hybrid_retrieve(conn, query_text, filters, top_k=DEFAULT_TOP_K)
            pool_ids = {(c["entity_type"], c["entity_id"]) for c in candidates}

            print(f"  candidate pool size: {len(candidates)}")
            print("  top 5 by similarity:")
            for c in candidates[:5]:
                print(f"    {c['similarity']:.3f}  {c['entity_type']:8s} {c['entity_id']:12s} {c['name']}")

            relevant = fetch_relevant_labels(conn, query_id)
            print(f"  grade>=2 labels ({len(relevant)}):")
            for entity_type, entity_id, grade in relevant:
                in_pool = (entity_type, entity_id) in pool_ids
                mark = "IN POOL" if in_pool else "MISSING"
                print(f"    grade={grade}  {entity_type:8s} {entity_id:12s}  [{mark}]")
                label_count += 1
                if in_pool:
                    hit_count += 1

        if label_count:
            print("=" * 80)
            print(f"Rough recall over this sample: {hit_count}/{label_count} grade>=2 labels found in-pool")
            print("(This is a hand-check sanity signal, not the real Block 5 retrieval-quality metric.)")


if __name__ == "__main__":
    main()
