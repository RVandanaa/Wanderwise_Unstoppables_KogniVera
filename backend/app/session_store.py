"""
Session Profile Store — Prakruti's piece (ARCHITECTURE.md § 2, Block 4).

Block 0 status: REAL, working implementation. This piece has no ML
dependency (it's just a dict keyed by session_id), so it's fully buildable
today rather than stubbed. Deliberately ephemeral and in-process only
(RISKS.md: not cross-device, does not survive a reload from a different
device) — this is the in-session learning signal, not a durable record.
"""
from collections import defaultdict

# session_id -> {"liked": set[entity_id], "dismissed": set[entity_id], "interaction_count": int}
_SESSIONS: dict[str, dict] = defaultdict(
    lambda: {"liked": set(), "dismissed": set(), "interaction_count": 0}
)


def record_interaction(session_id: str, entity_id: str, interaction_type: str) -> None:
    s = _SESSIONS[session_id]
    s["interaction_count"] += 1
    if interaction_type in ("like", "save", "book"):
        s["liked"].add(entity_id)
        s["dismissed"].discard(entity_id)
    elif interaction_type == "dismiss":
        s["dismissed"].add(entity_id)
        s["liked"].discard(entity_id)


def get_profile(session_id: str) -> dict:
    s = _SESSIONS[session_id]
    return {
        "session_id": session_id,
        "interaction_count": s["interaction_count"],
        "profile_vector_summary": {
            "liked_entities": sorted(s["liked"]),
            "dismissed_entities": sorted(s["dismissed"]),
        },
    }
