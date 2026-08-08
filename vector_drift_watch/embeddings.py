"""Deterministic embedding function used for the demo and tests.

This is a hashing-trick embedder (character trigrams hashed into a fixed
number of buckets, L2 normalized), not a semantic embedding model. It is
reproducible with no network calls and no model download, which is what lets
the drift math in drift.py be tested and demoed end to end in this sandbox.
Swap in a real model by implementing the same Embedder protocol (embed(text)
-> list[float] of fixed dimension) and passing it to the CLI instead; nothing
else in this repo assumes hashing specifically.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol


class Embedder(Protocol):
    dimension: int

    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    def __init__(self, dimension: int = 128, ngram: int = 3) -> None:
        self.dimension = dimension
        self.ngram = ngram

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        normalized = text.strip().lower()
        if not normalized:
            return vector

        grams = self._char_ngrams(normalized)
        for gram in grams:
            digest = hashlib.sha256(gram.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]

    def _char_ngrams(self, text: str) -> list[str]:
        padded = f"  {text}  "
        if len(padded) < self.ngram:
            return [padded]
        return [padded[i : i + self.ngram] for i in range(len(padded) - self.ngram + 1)]
