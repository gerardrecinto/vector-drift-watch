import pytest

from vector_drift_watch.drift import Snapshot, compare_snapshots, cosine_distance


def test_cosine_distance_identical_vectors_is_zero():
    assert cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)


def test_cosine_distance_orthogonal_vectors_is_one():
    assert cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)


def test_cosine_distance_opposite_vectors_is_two():
    assert cosine_distance([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(2.0)


def test_cosine_distance_dimension_mismatch_raises():
    with pytest.raises(ValueError):
        cosine_distance([1.0, 0.0], [1.0, 0.0, 0.0])


def test_cosine_distance_zero_vector_is_max_distance():
    assert cosine_distance([0.0, 0.0], [1.0, 0.0]) == 1.0


def test_snapshot_roundtrips_through_json():
    snap = Snapshot(taken_at=123.0, embeddings={"q1": [0.1, 0.2]})
    restored = Snapshot.from_json(snap.to_json())
    assert restored.taken_at == 123.0
    assert restored.embeddings == {"q1": [0.1, 0.2]}


def test_compare_snapshots_no_drift_when_embeddings_match():
    old = Snapshot(taken_at=1.0, embeddings={"q1": [1.0, 0.0], "q2": [0.0, 1.0]})
    new = Snapshot(taken_at=2.0, embeddings={"q1": [1.0, 0.0], "q2": [0.0, 1.0]})

    report = compare_snapshots(old, new)

    assert report.mean_distance == pytest.approx(0.0)
    assert report.max_distance == pytest.approx(0.0)


def test_compare_snapshots_flags_the_worst_drifted_query():
    old = Snapshot(taken_at=1.0, embeddings={"stable": [1.0, 0.0], "drifted": [1.0, 0.0]})
    new = Snapshot(taken_at=2.0, embeddings={"stable": [1.0, 0.0], "drifted": [0.0, 1.0]})

    report = compare_snapshots(old, new)

    assert report.max_distance_query == "drifted"
    assert report.max_distance == pytest.approx(1.0)
    assert report.mean_distance == pytest.approx(0.5)


def test_compare_snapshots_requires_shared_queries():
    old = Snapshot(taken_at=1.0, embeddings={"only_old": [1.0, 0.0]})
    new = Snapshot(taken_at=2.0, embeddings={"only_new": [0.0, 1.0]})

    with pytest.raises(ValueError):
        compare_snapshots(old, new)
