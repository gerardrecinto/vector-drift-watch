import math

from vector_drift_watch.embeddings import HashingEmbedder


def test_embed_is_deterministic():
    embedder = HashingEmbedder(dimension=64)
    a = embedder.embed("gpu node drain procedure")
    b = embedder.embed("gpu node drain procedure")
    assert a == b


def test_embed_dimension_matches_config():
    embedder = HashingEmbedder(dimension=32)
    vec = embedder.embed("some query")
    assert len(vec) == 32


def test_embed_is_unit_length_for_nonempty_text():
    embedder = HashingEmbedder(dimension=64)
    vec = embedder.embed("model serving timeout")
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-9


def test_embed_empty_string_is_zero_vector():
    embedder = HashingEmbedder(dimension=16)
    vec = embedder.embed("")
    assert vec == [0.0] * 16


def test_different_text_gives_different_vectors():
    embedder = HashingEmbedder(dimension=64)
    a = embedder.embed("gpu node drain procedure")
    b = embedder.embed("completely unrelated sentence about pagerduty")
    assert a != b
