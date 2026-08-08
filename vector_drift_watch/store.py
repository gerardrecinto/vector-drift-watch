"""pgvector-backed store: schema setup, upsert, nearest-neighbor query.

Talks to a real Postgres instance with the pgvector extension, normally the
one in docker-compose.yml. Connection details come from a plain libpq DSN
string so this works the same whether Postgres is in Docker, a CI service
container, or a local install.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extensions import connection as PgConnection


@dataclass(frozen=True)
class NeighborResult:
    doc_id: str
    text: str
    distance: float


class PgVectorStore:
    def __init__(self, dsn: str, dimension: int, table: str = "documents") -> None:
        self.dsn = dsn
        self.dimension = dimension
        self.table = table
        self._conn: PgConnection | None = None

    def connect(self) -> None:
        self._conn = psycopg2.connect(self.dsn)
        self._conn.autocommit = True
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "PgVectorStore":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def ensure_schema(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    doc_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding VECTOR({self.dimension}) NOT NULL
                )
                """
            )

    def upsert(self, doc_id: str, text: str, embedding: list[float]) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.table} (doc_id, text, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (doc_id) DO UPDATE SET text = EXCLUDED.text, embedding = EXCLUDED.embedding
                """,
                (doc_id, text, embedding),
            )

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self.table}")
            return cur.fetchone()[0]

    def query_nearest(self, embedding: list[float], k: int = 5) -> list[NeighborResult]:
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT doc_id, text, embedding <=> %s::vector AS distance
                FROM {self.table}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding, embedding, k),
            )
            return [NeighborResult(doc_id=r[0], text=r[1], distance=float(r[2])) for r in cur.fetchall()]
