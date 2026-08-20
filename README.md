# vector-drift-watch

CLI and small service that probes a vector store for query latency
(p50/p95/p99) and embedding drift over time (cosine distance shift between
snapshots of a fixed query set), and fires a Slack-webhook-shaped alert when
either crosses a threshold.

![demo](demo/demo.gif)

## What this is / isn't

Everything in the GIF above runs against a real local Postgres + pgvector
instance started by `docker-compose.yml`, and the latency numbers are
measured locally against that single-node container, not a claim about any
production deployment. The "embedding model version bump" step in the demo
is simulated (there's no second real model to swap in here): it takes one
snapshot with a 3-character n-gram hashing embedder and a second with a
2-character n-gram version of the same embedder, so the two embeddings are
genuinely different vectors, standing in for what a silent upstream model
change looks like. The cosine distance math and threshold check being
demonstrated are the real thing; only the two embedders being compared are
synthetic. See `vector_drift_watch/embeddings.py` for how to swap in a real
model.

## Why this exists

A RAG pipeline can look healthy on uptime and error rate while quietly
returning worse answers, because retrieval latency crept up or the upstream
embedding model changed and nobody watched for it. This tool watches both
signals against the same fixed query set, on the same schedule, so latency
regressions and embedding drift show up before someone notices retrieval
quality got worse.

## Architecture

```
fixed query set (config.py)
        |
        v
HashingEmbedder (embeddings.py)
        |
        v
PgVectorStore (store.py)  <---- psycopg2/pgvector ---->  Postgres + pgvector
        |                                                  (docker-compose)
        |
        +------------------------+------------------------+
        |                                                  |
        v                                                  v
LatencyProber (prober.py)                        DriftDetector (drift.py)
p50 / p95 / p99                                  cosine distance vs snapshot
        |                                                  |
        +------------------------+------------------------+
                                  |
                                  v
                     threshold check (alerts.py)
                                  |
                                  v
                  Slack-shaped webhook POST (mock in the demo)
```

## Running it

```bash
docker compose up -d
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

export VECTOR_DRIFT_WATCH_DATABASE_URL="postgresql://vdw:vdw@localhost:5432/vdw"
python -m vector_drift_watch.cli init-schema
python -m vector_drift_watch.cli ingest
python -m vector_drift_watch.cli probe --repeats 30
python -m vector_drift_watch.cli snapshot snapshots/baseline.json
python -m vector_drift_watch.cli snapshot snapshots/now.json
python -m vector_drift_watch.cli drift snapshots/baseline.json snapshots/now.json
python -m vector_drift_watch.cli watch --webhook-url http://127.0.0.1:8787 --cycles 1
```

`demo/mock_webhook.py` is a local stand-in for a Slack incoming webhook (see
"what this is / isn't" above); point `--webhook-url` at a real Slack webhook
URL to use this for real.

## CLI commands

| command | what it does |
|---|---|
| `init-schema` | creates the pgvector extension and the documents table |
| `ingest` | embeds and upserts a small demo corpus (`config.DEMO_CORPUS`) |
| `probe` | runs the fixed query set against the store `--repeats` times, reports p50/p95/p99 latency |
| `snapshot <path>` | embeds the fixed query set and writes it to a JSON snapshot file |
| `drift <old> <new>` | compares two snapshots, reports mean/max cosine distance |
| `watch` | loops probe + snapshot + drift + threshold check + webhook alert |

## Thresholds

Set in `vector_drift_watch/config.py`: `DEFAULT_LATENCY_P95_THRESHOLD_MS =
50.0`, `DEFAULT_DRIFT_THRESHOLD = 0.15` cosine distance. Both are plain
constants, not tuned against any real production traffic.

## Alert escalation

`watch` requires a check (latency or drift) to breach its threshold on
`--consecutive-breaches` back-to-back cycles (default 2) before it posts to
the webhook, so a single noisy sample doesn't page anyone. This is the
`doc-pagerduty-escalation` guidance from the demo corpus itself, actually
implemented: "require two consecutive probe cycles over threshold before
escalating." Pass `--consecutive-breaches 1` to alert on every single
breach instead. `watch --json-out` prints one JSON line per cycle
(`p95_ms`, `max_drift`, `breached`, `escalated`, `webhook_posted`) instead
of the human-readable summary, for piping into a log processor.

## Docker

```bash
docker compose up -d
docker build -t vector-drift-watch .
docker run --rm --network vector-drift-watch_default \
  -e VECTOR_DRIFT_WATCH_DATABASE_URL="postgresql://vdw:vdw@postgres:5432/vdw" \
  vector-drift-watch probe --repeats 30
```

## Tests

```bash
docker compose up -d
pip install -r requirements-dev.txt
export VECTOR_DRIFT_WATCH_DATABASE_URL="postgresql://vdw:vdw@localhost:5432/vdw"
pytest -v
```

Unit tests (embeddings, drift math, percentile math, alert payloads and
threshold checks) run with no dependencies. `tests/test_store_integration.py`
needs a reachable Postgres and is skipped automatically if one isn't
present; CI brings up the same `pgvector/pgvector:pg16` image as a service
container so it runs there too.

## Repo layout

```
vector_drift_watch/
  embeddings.py   # deterministic hashing embedder (see "what this is / isn't")
  store.py        # pgvector-backed store: schema, upsert, nearest-neighbor query
  prober.py       # latency percentile math, query_fn is injected for testability
  drift.py        # snapshot + cosine distance comparison
  alerts.py       # threshold checks + Slack-shaped payload + webhook POST
  config.py       # demo corpus, fixed query set, thresholds
  cli.py          # click CLI wiring the above together
tests/
demo/
  run_demo.sh
  simulate_drift.py
  mock_webhook.py
docker-compose.yml
Dockerfile
```
