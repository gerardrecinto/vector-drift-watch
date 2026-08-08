"""Simulates an embedding model version bump for the demo.

There's no second real embedding model to swap in here, so this takes one
snapshot with HashingEmbedder(ngram=3) and a second with
HashingEmbedder(ngram=2) against the same fixed query set, standing in for
"someone upstream changed the embedding model between two runs." The cosine
distance math and threshold check are the real thing being demonstrated;
only the two embedders being compared are synthetic.
"""

from __future__ import annotations

from vector_drift_watch import config
from vector_drift_watch.alerts import Thresholds, check_drift
from vector_drift_watch.drift import compare_snapshots, take_snapshot
from vector_drift_watch.embeddings import HashingEmbedder


def main() -> None:
    before = HashingEmbedder(dimension=config.DEFAULT_EMBEDDING_DIMENSION, ngram=3)
    after = HashingEmbedder(dimension=config.DEFAULT_EMBEDDING_DIMENSION, ngram=2)

    snap_before = take_snapshot(config.DEMO_QUERIES, before.embed)
    snap_after = take_snapshot(config.DEMO_QUERIES, after.embed)

    report = compare_snapshots(snap_before, snap_after)

    print(f"mean cosine distance across {len(config.DEMO_QUERIES)} queries: {report.mean_distance:.4f}")
    print(f"max cosine distance: {report.max_distance:.4f} (query: {report.max_distance_query!r})")

    check = check_drift(
        report.max_distance, report.max_distance_query, Thresholds(0, config.DEFAULT_DRIFT_THRESHOLD)
    )
    print(f"threshold check: {check.reason}")


if __name__ == "__main__":
    main()
