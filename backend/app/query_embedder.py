"""
Loads paraphrase-multilingual-MiniLM-L12-v2 once at process startup and
embeds each incoming query into the same vector space `embed_catalogue.py`
(Block 1) used offline for the catalogue. Must stay in lockstep with that
script: same model name, same `normalize_embeddings=True` — a mismatch on
either would silently degrade every similarity score without erroring.
"""

from __future__ import annotations

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_query(text: str):
    """Returns a normalized embedding vector (list[float], len 384) for one query string.

    Called per-request, so this stays cheap (single short string, no batching
    needed) — the model itself is the expensive one-time cost, paid once at
    first call / app startup, not per request.
    """
    model = get_model()
    vector = model.encode([text], normalize_embeddings=True)[0]
    return vector


def warm_up():
    """Called from FastAPI startup and before the live demo (RISKS.md § 5, § 8)
    so the first real request isn't the one paying the model-load cost."""
    get_model()
    embed_query("warm up")
