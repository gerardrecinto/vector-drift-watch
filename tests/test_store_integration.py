"""Integration test against a real Postgres + pgvector instance.

Reads VECTOR_DRIFT_WATCH_DATABASE_URL (same env var the CLI uses), defaulting
to the docker-compose service. Skipped if that Postgres isn't reachable, so
this suite still runs (minus this file) in environments without Docker; CI
brings up the same pgvector image as a service container so it runs there.
"""

import psycopg2
import pytest

from vector_drift_watch.config import DEFAULT_DATABASE_URL
from vector_drift_watch.embeddings import HashingEmbedder
from vector_drift_watch.store import PgVectorStore


def _postgres_reachable(dsn: str) -> bool:
    try:
        conn = psycopg2.connect(dsn, connect_timeout=2)
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


DSN = DEFAULT_DATABASE_URL
pytestmark = pytest.mark.skipif(
    not _postgres_reachable(DSN), reason="no reachable Postgres at VECTOR_DRIFT_WATCH_DATABASE_URL"
)


@pytest.fixture
def store():
    embedder = HashingEmbedder(dimension=32)
    with PgVectorStore(DSN, dimension=32, table="test_documents") as s:
        s.ensure_schema()
        with s._conn.cursor() as cur:
            cur.execute("DELETE FROM test_documents")
        yield s, embedder
        with s._conn.cursor() as cur:
            cur.execute("DELETE FROM test_documents")


def test_upsert_and_count(store):
    s, embedder = store
    s.upsert("doc1", "gpu node drain procedure", embedder.embed("gpu node drain procedure"))
    s.upsert("doc2", "pagerduty escalation policy", embedder.embed("pagerduty escalation policy"))
    assert s.count() == 2


def test_upsert_is_idempotent_on_doc_id(store):
    s, embedder = store
    s.upsert("doc1", "version one", embedder.embed("version one"))
    s.upsert("doc1", "version two", embedder.embed("version two"))
    assert s.count() == 1


def test_query_nearest_returns_closest_match_first(store):
    s, embedder = store
    s.upsert("gpu", "gpu node drain procedure", embedder.embed("gpu node drain procedure"))
    s.upsert("pd", "pagerduty escalation policy", embedder.embed("pagerduty escalation policy"))
    s.upsert("rag", "rag retrieval quality degrades", embedder.embed("rag retrieval quality degrades"))

    results = s.query_nearest(embedder.embed("how do I drain a gpu node"), k=3)

    assert results[0].doc_id == "gpu"
    assert results[0].distance <= results[1].distance <= results[2].distance
