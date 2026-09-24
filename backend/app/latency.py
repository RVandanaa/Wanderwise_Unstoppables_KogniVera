"""
latency.py — small helper for the per-stage latency logging RISKS.md § 5 and
the Block 3 smoke test require: "a per-stage latency budget (retrieval <
300ms, rerank+MMR < 100ms, explanation < 50ms, end-to-end < 600ms) set and
logged during the Block 3 smoke test, not assumed."

Usage:
    from latency import Stopwatch, BUDGET_MS

    sw = Stopwatch()
    with sw.stage("retrieval"):
        candidates = retrieval.hybrid_retrieve(...)
    with sw.stage("rerank_mmr"):
        results = rerank.rerank(candidates)

    sw.log_if_over_budget()   # warns per-stage if any budget was exceeded
    sw.as_dict()              # -> {"retrieval": 210, "rerank_mmr": 65, "total": 275}
                              #    (matches API_SPEC.md's latency_ms shape)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

log = logging.getLogger("latency")

# ARCHITECTURE.md § 5 — enforced, not aspirational.
BUDGET_MS = {
    "retrieval": 300,
    "rerank_mmr": 100,
    "explanation": 50,
    "total": 600,
}


class Stopwatch:
    def __init__(self):
        self.timings_ms: dict[str, int] = {}

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.timings_ms[name] = int((time.perf_counter() - t0) * 1000)

    def total(self) -> int:
        return sum(v for k, v in self.timings_ms.items() if k != "total")

    def as_dict(self) -> dict[str, int]:
        return {**self.timings_ms, "total": self.total()}

    def log_if_over_budget(self):
        """RISKS.md § 5's stated first lever if a stage is over budget:
        cutting candidate-pool size (top-50 -> top-20) before touching
        anything else — this function only reports the breach, it doesn't
        apply that lever itself, since that's a retrieval.py-level change.
        """
        for stage, budget in BUDGET_MS.items():
            actual = self.timings_ms.get(stage) if stage != "total" else self.total()
            if actual is not None and actual > budget:
                log.warning("Stage '%s' took %dms, over the %dms budget (ARCHITECTURE.md § 5)", stage, actual, budget)
