"""Embedding drift: snapshot a fixed query set's embeddings, compare two
snapshots with cosine distance.

A snapshot is just {query: embedding} plus a timestamp, serialized to JSON so
it can be diffed across runs (e.g. today's snapshot vs last week's) without
needing the vector store itself to still have history.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass


def cosine_distance(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    cosine_similarity = dot / (norm_a * norm_b)
    cosine_similarity = max(-1.0, min(1.0, cosine_similarity))
    return 1.0 - cosine_similarity


@dataclass(frozen=True)
class Snapshot:
    taken_at: float
    embeddings: dict[str, list[float]]

    def to_json(self) -> str:
        return json.dumps({"taken_at": self.taken_at, "embeddings": self.embeddings})

    @staticmethod
    def from_json(raw: str) -> "Snapshot":
        data = json.loads(raw)
        return Snapshot(taken_at=data["taken_at"], embeddings=data["embeddings"])


@dataclass(frozen=True)
class QueryDrift:
    query: str
    distance: float


@dataclass(frozen=True)
class DriftReport:
    query_drifts: list[QueryDrift]
    mean_distance: float
    max_distance: float
    max_distance_query: str


def take_snapshot(queries: list[str], embed_fn) -> Snapshot:
    embeddings = {query: embed_fn(query) for query in queries}
    return Snapshot(taken_at=time.time(), embeddings=embeddings)


def compare_snapshots(old: Snapshot, new: Snapshot) -> DriftReport:
    shared_queries = [q for q in old.embeddings if q in new.embeddings]
    if not shared_queries:
        raise ValueError("snapshots share no queries, nothing to compare")

    drifts = [
        QueryDrift(query=q, distance=cosine_distance(old.embeddings[q], new.embeddings[q]))
        for q in shared_queries
    ]
    distances = [d.distance for d in drifts]
    worst = max(drifts, key=lambda d: d.distance)

    return DriftReport(
        query_drifts=drifts,
        mean_distance=sum(distances) / len(distances),
        max_distance=worst.distance,
        max_distance_query=worst.query,
    )
