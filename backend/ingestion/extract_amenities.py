"""
extract_amenities.py — Block 3 (hours 8-12), owner: Vandanaa.

Keyword-extracts amenity tags from hotels.description into
hotel_amenity_tags (data/migrations/002_hotel_amenity_tags.sql). This is a
soft rerank signal only — never a hard filter (DATA_MODEL.md Rule R1) —
because free-text keyword matching WILL misclassify some hotels, most often
a false positive from negated text ("no pool", "not wheelchair accessible")
(RISKS.md § 2).

Negation handling (RISKS.md § 2's stated fallback): for every keyword match,
look at the +/-5 token window around it; if a negation term appears in that
window, drop the tag rather than keep it. This is deliberately a blunt
window check, not real NLP dependency parsing — good enough to catch the
common "no X" / "without X" pattern the risk names, not a claim of high
precision on subtler negation.

AMENITY_KEYWORDS covers exactly the four amenities DATA_MODEL.md names as
appearing in eval_queries filters: swimming_pool, free_wifi,
step_free_access, family_rooms. Extend this list only after checking whether
eval_queries actually asks about anything else — extraction effort should
track what the eval set (and demo query) can exercise, not the full space of
things a hotel description might mention.

Every tag lands with confirmed = false. Nothing here confirms a tag — that's
a human, doing the manual spot-check pass (RISKS.md § 2, EVALUATION.md
"Amenity-tag quality"), via scripts/spot_check_amenities.py. An unconfirmed
tag should not be trusted as a demo-day rerank signal until someone has
actually looked at it.
"""

from __future__ import annotations

import argparse
import logging
import re

from db import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("extract_amenities")

NEGATION_TERMS = {"no", "not", "without", "lacks", "lacking", "none", "n't"}
WINDOW = 5  # tokens either side of a match, per RISKS.md § 2

# amenity -> list of phrases that indicate it; longer phrases first isn't
# required here since matching is independent per phrase, not greedy.
AMENITY_KEYWORDS: dict[str, list[str]] = {
    "swimming_pool": ["swimming pool", "pool"],
    "free_wifi": ["free wifi", "free wi-fi", "complimentary wifi", "wi-fi", "wifi"],
    "step_free_access": [
        "step-free access",
        "step free access",
        "wheelchair accessible",
        "wheelchair-accessible",
        "wheelchair access",
        "ramp access",
    ],
    "family_rooms": ["family room", "family rooms", "family-friendly room"],
}

_token_re = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> list[str]:
    return _token_re.findall(text.lower())


def phrase_token_len(phrase: str) -> int:
    return len(tokenize(phrase))


def find_phrase_spans(tokens: list[str], phrase_tokens: list[str]) -> list[tuple[int, int]]:
    """Returns [(start, end_exclusive), ...] token index spans where phrase_tokens occurs in tokens."""
    spans = []
    n, m = len(tokens), len(phrase_tokens)
    if m == 0:
        return spans
    for i in range(n - m + 1):
        if tokens[i : i + m] == phrase_tokens:
            spans.append((i, i + m))
    return spans


def is_negated(tokens: list[str], span: tuple[int, int]) -> bool:
    start, end = span
    window = tokens[max(0, start - WINDOW) : start] + tokens[end : end + WINDOW]
    return any(t in NEGATION_TERMS for t in window)


def extract_amenities_from_text(description: str) -> tuple[set[str], list[str]]:
    """Returns (confirmed_candidate_tags, dropped_negated_tags) — the second
    list exists purely so the caller can log what got filtered, for the
    spot-check pass to sanity-check the negation logic itself, not just the
    surviving tags."""
    tokens = tokenize(description)
    found = set()
    dropped = []

    for amenity, phrases in AMENITY_KEYWORDS.items():
        if amenity in found:
            continue
        for phrase in phrases:
            phrase_tokens = tokenize(phrase)
            for span in find_phrase_spans(tokens, phrase_tokens):
                if is_negated(tokens, span):
                    dropped.append(amenity)
                else:
                    found.add(amenity)
                    break
            if amenity in found:
                break

    return found, dropped


def fetch_hotel_descriptions(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT hotel_id, description FROM hotels WHERE status = 'active'")
        return cur.fetchall()


def replace_tags(conn, hotel_id: str, tags: set[str]):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM hotel_amenity_tags WHERE hotel_id = %s", (hotel_id,))
        if tags:
            cur.executemany(
                "INSERT INTO hotel_amenity_tags (hotel_id, amenity, confirmed) VALUES (%s, %s, false)",
                [(hotel_id, tag) for tag in tags],
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print what would be tagged, write nothing")
    args = parser.parse_args()

    conn = get_connection()
    try:
        rows = fetch_hotel_descriptions(conn)
        log.info("Scanning %d active hotels", len(rows))

        amenity_counts: dict[str, int] = {a: 0 for a in AMENITY_KEYWORDS}
        negation_drop_count = 0

        for hotel_id, description in rows:
            if not description:
                continue
            tags, dropped = extract_amenities_from_text(description)
            negation_drop_count += len(dropped)
            for tag in tags:
                amenity_counts[tag] += 1

            if args.dry_run:
                if tags or dropped:
                    log.info("  %s  tags=%s  negated_dropped=%s", hotel_id, sorted(tags), dropped)
            else:
                replace_tags(conn, hotel_id, tags)

        if not args.dry_run:
            conn.commit()

        log.info("Done%s.", " (dry run — nothing written)" if args.dry_run else "")
        for amenity, count in amenity_counts.items():
            log.info("  %-18s %d hotels tagged", amenity, count)
        log.info("  negation-window drops (kept off the tag list): %d", negation_drop_count)
        log.info("Next: python scripts/spot_check_amenities.py  (RISKS.md § 2 manual review, before demo)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
