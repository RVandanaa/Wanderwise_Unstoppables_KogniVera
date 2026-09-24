"""
Pydantic models for the /search contract in API_SPEC.md. Kept in one place
so Block 3 (rerank), Block 4 (Query Guard), and the eval harness (Block 5)
all import the same shapes instead of each redefining them.

Money fields are `str`, never `float` (Data Rule R3, DATA_MODEL.md) — a
client that sends `"price_max": 4000` (a JSON number) instead of
`"price_max": "4000.00"` (a string) is a validation error, not a silent
float coercion.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EntityType = Literal["hotel", "poi", "package"]


class SearchFilters(BaseModel):
    city_id: str | None = None
    price_max: str | None = None  # decimal string, e.g. "4000.00" — see module docstring
    star_min: int | None = None
    category: str | None = None  # categories.code, snake_case (Data Rule R5)
    amenities: list[str] = Field(default_factory=list)  # soft signal only — DATA_MODEL.md Rule R1

    @field_validator("price_max")
    @classmethod
    def price_max_is_decimal(cls, v):
        if v is None:
            return v
        try:
            Decimal(v)
        except Exception as e:
            raise ValueError(f"price_max must be a decimal string, got {v!r}") from e
        return v


class SearchRequest(BaseModel):
    session_id: str
    user_id: str | None = None
    query_text: str
    language: str  # BCP-47 tag, e.g. "en-IN", "hi", "ta" — Data Rule R6
    filters: SearchFilters = Field(default_factory=SearchFilters)
    top_k: int = 10


class ResultItem(BaseModel):
    entity_type: EntityType
    entity_id: str
    name: str
    score: float
    explanation: str | None = None
    moved_up: bool | None = None


class QueryGuardInfo(BaseModel):
    relaxed: bool = False
    relaxed_filter: str | None = None
    narrow_results: bool = False
    candidate_pool_size: int = 0


class LatencyBreakdown(BaseModel):
    retrieval: int = 0
    rerank_mmr: int = 0
    explanation: int = 0
    total: int = 0


class SearchResponse(BaseModel):
    results: list[ResultItem]
    query_guard: QueryGuardInfo
    latency_ms: LatencyBreakdown
