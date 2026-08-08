#!/bin/bash
set -e
cd "$(dirname "$0")/.."

export VECTOR_DRIFT_WATCH_DATABASE_URL="postgresql://vdw:vdw@localhost:5432/vdw"
PY=.venv/bin/python
export PYTHONPATH=.

echo '$ docker compose up -d'
docker compose up -d >/dev/null 2>&1
echo "waiting for postgres to be healthy..."
for i in $(seq 1 20); do
  status=$(docker inspect -f '{{.State.Health.Status}}' vector-drift-watch-postgres-1 2>/dev/null || echo starting)
  [ "$status" = "healthy" ] && break
  sleep 1
done

echo
echo '$ python -m vector_drift_watch.cli init-schema'
$PY -m vector_drift_watch.cli init-schema

echo
echo '$ python -m vector_drift_watch.cli ingest'
$PY -m vector_drift_watch.cli ingest

echo
echo '$ python -m vector_drift_watch.cli probe --repeats 30'
$PY -m vector_drift_watch.cli probe --repeats 30

echo
echo '$ python -m vector_drift_watch.cli snapshot snapshots/baseline.json'
rm -rf snapshots && mkdir -p snapshots
$PY -m vector_drift_watch.cli snapshot snapshots/baseline.json
sleep 1
echo '$ python -m vector_drift_watch.cli snapshot snapshots/now.json'
$PY -m vector_drift_watch.cli snapshot snapshots/now.json

echo
echo '$ python -m vector_drift_watch.cli drift snapshots/baseline.json snapshots/now.json'
$PY -m vector_drift_watch.cli drift snapshots/baseline.json snapshots/now.json

echo
echo "# simulating an embedding model version bump between two snapshots"
echo '$ python demo/simulate_drift.py'
$PY demo/simulate_drift.py

echo
echo "# starting a local mock webhook receiver (stands in for a Slack incoming webhook)"
$PY demo/mock_webhook.py > /tmp/vdw_webhook.log 2>&1 &
WEBHOOK_PID=$!
sleep 1

echo '$ python -m vector_drift_watch.cli watch --webhook-url http://127.0.0.1:8787 --cycles 1'
$PY -m vector_drift_watch.cli watch --webhook-url http://127.0.0.1:8787 --cycles 1 --interval 1

kill $WEBHOOK_PID 2>/dev/null || true

echo
docker compose down >/dev/null 2>&1
echo "stack stopped."
