"""
spot_check_amenities.py — supports the manual review pass required by
RISKS.md § 2 and EVALUATION.md "Amenity-tag quality": extraction is
keyword-based and will misclassify some hotels, so nothing here is trusted
for the demo until a person has looked at it.

Two modes:

    python scripts/spot_check_amenities.py --sample 30
        Random ~30-hotel sample (RISKS.md § 2's stated sample size),
        printing each hotel's description next to its extracted tags so a
        person can eyeball false positives/negatives.

    python scripts/spot_check_amenities.py --amenity step_free_access --confirm
        Prints EVERY hotel tagged step_free_access, not a sample —
        RISKS.md § 2 / EVALUATION.md specifically call out step_free_access
        for full review (it's the filter used in the PRD § 4 demo scenario),
        not just a spot sample. With --confirm, after you've reviewed the
        printout, it flips confirmed = true for the ones you approve
        interactively.

Nothing is auto-confirmed. Per extract_amenities.py's docstring: an
unconfirmed tag should not be trusted as a rerank signal until this script
(or an equivalent manual look) has actually happened.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "ingestion"))

from db import get_connection  # noqa: E402


def fetch_sample(conn, n: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT h.hotel_id, h.description, array_agg(t.amenity ORDER BY t.amenity) FILTER (WHERE t.amenity IS NOT NULL)
            FROM hotels h
            LEFT JOIN hotel_amenity_tags t ON t.hotel_id = h.hotel_id
            WHERE h.status = 'active'
            GROUP BY h.hotel_id, h.description
            ORDER BY random()
            LIMIT %s
            """,
            (n,),
        )
        return cur.fetchall()


def fetch_by_amenity(conn, amenity: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT h.hotel_id, h.description, t.confirmed
            FROM hotel_amenity_tags t
            JOIN hotels h ON h.hotel_id = t.hotel_id
            WHERE t.amenity = %s
            ORDER BY h.hotel_id
            """,
            (amenity,),
        )
        return cur.fetchall()


def confirm_tags(conn, amenity: str, hotel_ids: list[str]):
    if not hotel_ids:
        return
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE hotel_amenity_tags SET confirmed = true WHERE hotel_id = %s AND amenity = %s",
            [(hid, amenity) for hid in hotel_ids],
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=None, help="random N-hotel sample review")
    parser.add_argument("--amenity", default=None, help="review every hotel tagged with this amenity")
    parser.add_argument("--confirm", action="store_true", help="interactively confirm each row in --amenity mode")
    args = parser.parse_args()

    if not args.sample and not args.amenity:
        args.sample = 30  # RISKS.md § 2 default sample size

    with get_connection() as conn:
        if args.amenity:
            rows = fetch_by_amenity(conn, args.amenity)
            print(f"{len(rows)} hotels tagged '{args.amenity}':\n")
            approved = []
            for hotel_id, description, confirmed in rows:
                print("=" * 80)
                print(f"{hotel_id}  (confirmed={confirmed})")
                print(description)
                if args.confirm and not confirmed:
                    answer = input("Confirm this tag? [y/N] ").strip().lower()
                    if answer == "y":
                        approved.append(hotel_id)
            if args.confirm:
                confirm_tags(conn, args.amenity, approved)
                print(f"\nConfirmed {len(approved)}/{len(rows)}.")
        else:
            rows = fetch_sample(conn, args.sample)
            print(f"Random sample of {len(rows)} active hotels:\n")
            for hotel_id, description, tags in rows:
                print("=" * 80)
                print(f"{hotel_id}   tags: {tags or []}")
                print(description)
            print(
                "\nLook for: a tag with no textual support, a missed tag the "
                "description clearly supports, or a bare 'pool' match that's "
                "actually 'pool table'/'car pool' rather than a swimming pool "
                "— that keyword is the most likely false-positive source "
                "(see extract_amenities.py AMENITY_KEYWORDS)."
            )


if __name__ == "__main__":
    main()
