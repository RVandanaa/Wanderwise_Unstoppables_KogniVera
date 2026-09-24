-- 002_hotel_amenity_tags.sql
--
-- Block 3 (hours 8-12), owner: Vandanaa.
-- Rule R1 (DATA_MODEL.md): additive only — sits beside `hotels`, never
-- inside it. Derived, keyword-extracted from hotels.description,
-- negation-checked (RISKS.md § 2). Soft rerank signal ONLY — Prakruti's
-- rerank.py must never use this as a hard filter (DATA_MODEL.md Rule R1).
--
-- Run this AFTER 001_item_embeddings.sql and BEFORE
-- backend/ingestion/extract_amenities.py.
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS hotel_amenity_tags (
    hotel_id      text        NOT NULL REFERENCES hotels(hotel_id),
    amenity       text        NOT NULL,
    confirmed     boolean     NOT NULL DEFAULT false, -- flips true only after
                                                       -- the manual spot-check
                                                       -- pass (RISKS.md § 2,
                                                       -- EVALUATION.md); an
                                                       -- unconfirmed tag is
                                                       -- pulled, not shipped
    extracted_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (hotel_id, amenity)
);

-- Prakruti's rerank reads this to nudge score for hotels matching a
-- traveller's requested amenity — indexed on hotel_id since that's always
-- the lookup direction (given a candidate hotel, what tags does it have),
-- never the other way round.
CREATE INDEX IF NOT EXISTS hotel_amenity_tags_hotel_idx
    ON hotel_amenity_tags (hotel_id);
