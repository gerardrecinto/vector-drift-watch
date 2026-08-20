"""CLI for vector-drift-watch: init-schema, ingest, probe, snapshot, drift, watch."""

from __future__ import annotations

import json
import time
from pathlib import Path

import click

from vector_drift_watch import config
from vector_drift_watch.alerts import (
    ConsecutiveBreachTracker,
    Thresholds,
    build_slack_payload,
    check_drift,
    check_latency,
    fire_alert,
)
from vector_drift_watch.drift import Snapshot, compare_snapshots, take_snapshot
from vector_drift_watch.embeddings import HashingEmbedder
from vector_drift_watch.prober import probe_latency
from vector_drift_watch.store import PgVectorStore


@click.group()
@click.option("--database-url", default=config.DEFAULT_DATABASE_URL, envvar="VECTOR_DRIFT_WATCH_DATABASE_URL")
@click.option("--dimension", default=config.DEFAULT_EMBEDDING_DIMENSION, type=int)
@click.pass_context
def cli(ctx: click.Context, database_url: str, dimension: int) -> None:
    ctx.ensure_object(dict)
    ctx.obj["database_url"] = database_url
    ctx.obj["dimension"] = dimension
    ctx.obj["embedder"] = HashingEmbedder(dimension=dimension)


@cli.command("init-schema")
@click.pass_context
def init_schema(ctx: click.Context) -> None:
    with PgVectorStore(ctx.obj["database_url"], ctx.obj["dimension"]) as store:
        store.ensure_schema()
    click.echo("schema ready")


@cli.command("ingest")
@click.pass_context
def ingest(ctx: click.Context) -> None:
    embedder = ctx.obj["embedder"]
    with PgVectorStore(ctx.obj["database_url"], ctx.obj["dimension"]) as store:
        store.ensure_schema()
        for doc_id, text in config.DEMO_CORPUS.items():
            store.upsert(doc_id, text, embedder.embed(text))
        count = store.count()
    click.echo(f"ingested demo corpus, {count} documents in the store")


@cli.command("probe")
@click.option("--repeats", default=20, type=int)
@click.option("--json-out", "json_out", is_flag=True)
@click.pass_context
def probe(ctx: click.Context, repeats: int, json_out: bool) -> None:
    embedder = ctx.obj["embedder"]
    with PgVectorStore(ctx.obj["database_url"], ctx.obj["dimension"]) as store:

        def query_fn(text: str):
            return store.query_nearest(embedder.embed(text), k=3)

        report = probe_latency(config.DEMO_QUERIES, query_fn, repeats=repeats)

    if json_out:
        click.echo(json.dumps(report.__dict__))
    else:
        click.echo(f"samples={report.sample_count}")
        click.echo(f"p50={report.p50_ms:.2f}ms  p95={report.p95_ms:.2f}ms  p99={report.p99_ms:.2f}ms")
        click.echo(f"max={report.max_ms:.2f}ms")

    threshold_check = check_latency(report.p95_ms, Thresholds(config.DEFAULT_LATENCY_P95_THRESHOLD_MS, 0))
    if threshold_check.fired:
        click.echo(f"ALERT: {threshold_check.reason}")


@cli.command("snapshot")
@click.argument("output_path", type=click.Path())
@click.pass_context
def snapshot(ctx: click.Context, output_path: str) -> None:
    embedder = ctx.obj["embedder"]
    snap = take_snapshot(config.DEMO_QUERIES, embedder.embed)
    Path(output_path).write_text(snap.to_json())
    click.echo(f"snapshot of {len(config.DEMO_QUERIES)} queries written to {output_path}")


@cli.command("drift")
@click.argument("old_path", type=click.Path(exists=True))
@click.argument("new_path", type=click.Path(exists=True))
@click.option("--json-out", "json_out", is_flag=True)
def drift(old_path: str, new_path: str, json_out: bool) -> None:
    old_snap = Snapshot.from_json(Path(old_path).read_text())
    new_snap = Snapshot.from_json(Path(new_path).read_text())
    report = compare_snapshots(old_snap, new_snap)

    if json_out:
        click.echo(
            json.dumps(
                {
                    "mean_distance": report.mean_distance,
                    "max_distance": report.max_distance,
                    "max_distance_query": report.max_distance_query,
                    "per_query": [{"query": d.query, "distance": d.distance} for d in report.query_drifts],
                }
            )
        )
    else:
        click.echo(f"mean cosine distance: {report.mean_distance:.4f}")
        click.echo(f"max cosine distance: {report.max_distance:.4f} ({report.max_distance_query!r})")

    threshold_check = check_drift(
        report.max_distance, report.max_distance_query, Thresholds(0, config.DEFAULT_DRIFT_THRESHOLD)
    )
    if threshold_check.fired:
        click.echo(f"ALERT: {threshold_check.reason}")


@cli.command("watch")
@click.option("--webhook-url", default=None)
@click.option("--interval", default=30.0, type=float)
@click.option("--baseline-path", default="snapshots/baseline.json", type=click.Path())
@click.option("--cycles", default=0, type=int, help="0 means run forever")
@click.option(
    "--consecutive-breaches",
    default=2,
    type=int,
    help=(
        "require this many back-to-back over-threshold cycles per check before "
        "webhook-alerting, so a single noisy sample doesn't page (see "
        "doc-pagerduty-escalation in config.DEMO_CORPUS). 1 alerts on every breach."
    ),
)
@click.option("--json-out", "json_out", is_flag=True, help="print each cycle summary as a JSON line")
@click.pass_context
def watch(
    ctx: click.Context,
    webhook_url: str | None,
    interval: float,
    baseline_path: str,
    cycles: int,
    consecutive_breaches: int,
    json_out: bool,
) -> None:
    embedder = ctx.obj["embedder"]
    baseline_file = Path(baseline_path)
    baseline_file.parent.mkdir(parents=True, exist_ok=True)

    if not baseline_file.exists():
        baseline = take_snapshot(config.DEMO_QUERIES, embedder.embed)
        baseline_file.write_text(baseline.to_json())
        if not json_out:
            click.echo(f"no baseline found, wrote one to {baseline_path}")
    else:
        baseline = Snapshot.from_json(baseline_file.read_text())

    breach_tracker = ConsecutiveBreachTracker(required_streak=consecutive_breaches)

    cycle = 0
    while cycles == 0 or cycle < cycles:
        cycle += 1
        with PgVectorStore(ctx.obj["database_url"], ctx.obj["dimension"]) as store:

            def query_fn(text: str):
                return store.query_nearest(embedder.embed(text), k=3)

            latency_report = probe_latency(config.DEMO_QUERIES, query_fn, repeats=10)

        current = take_snapshot(config.DEMO_QUERIES, embedder.embed)
        drift_report = compare_snapshots(baseline, current)

        checks = {
            "latency": check_latency(
                latency_report.p95_ms, Thresholds(config.DEFAULT_LATENCY_P95_THRESHOLD_MS, 0)
            ),
            "drift": check_drift(
                drift_report.max_distance,
                drift_report.max_distance_query,
                Thresholds(0, config.DEFAULT_DRIFT_THRESHOLD),
            ),
        }

        escalated = [
            check for name, check in checks.items() if breach_tracker.record(name, check.fired)
        ]

        webhook_posted: bool | None = None
        if escalated and webhook_url:
            payload = build_slack_payload(f"cycle {cycle}", escalated)
            webhook_posted = fire_alert(webhook_url, payload)

        if json_out:
            click.echo(
                json.dumps(
                    {
                        "cycle": cycle,
                        "p95_ms": latency_report.p95_ms,
                        "max_drift": drift_report.max_distance,
                        "breached": [name for name, c in checks.items() if c.fired],
                        "escalated": [c.reason for c in escalated],
                        "webhook_posted": webhook_posted,
                    }
                )
            )
        else:
            click.echo(
                f"cycle {cycle}: p95={latency_report.p95_ms:.2f}ms  "
                f"max_drift={drift_report.max_distance:.4f}  "
                f"breaches={sum(1 for c in checks.values() if c.fired)}  "
                f"escalated={len(escalated)}"
            )
            if webhook_posted is not None:
                click.echo(f"alert webhook posted: {webhook_posted}")

        if cycles == 0 or cycle < cycles:
            time.sleep(interval)


if __name__ == "__main__":
    cli()
