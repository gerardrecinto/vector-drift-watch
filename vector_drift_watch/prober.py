"""Latency probing: run a fixed query set N times, report p50/p95/p99.

query_fn is injected so this module has no dependency on PgVectorStore and
can be unit tested with a fake timing source.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class LatencyReport:
    sample_count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = rank - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def probe_latency(
    queries: list[str],
    query_fn: Callable[[str], object],
    repeats: int = 1,
    clock: Callable[[], float] = time.perf_counter,
) -> LatencyReport:
    """Runs query_fn(query) for every query in queries, `repeats` times each,
    and returns a percentile report over wall clock latency in milliseconds.
    """
    samples: list[float] = []
    for _ in range(repeats):
        for query in queries:
            start = clock()
            query_fn(query)
            elapsed_ms = (clock() - start) * 1000.0
            samples.append(elapsed_ms)

    samples.sort()
    return LatencyReport(
        sample_count=len(samples),
        p50_ms=percentile(samples, 50),
        p95_ms=percentile(samples, 95),
        p99_ms=percentile(samples, 99),
        max_ms=samples[-1] if samples else 0.0,
    )
