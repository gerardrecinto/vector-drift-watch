"""Threshold checks and a Slack-webhook-shaped alert payload.

fire_alert posts to whatever URL it's given; in the demo that's a local
mock receiver (see demo/mock_webhook.py), not a real Slack workspace. The
payload shape (text + blocks) matches Slack's incoming webhook format so
swapping in a real Slack webhook URL is a config change, not a code change.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class Thresholds:
    latency_p95_ms: float
    drift_distance: float


@dataclass(frozen=True)
class AlertCheck:
    fired: bool
    reason: str


def check_latency(p95_ms: float, thresholds: Thresholds) -> AlertCheck:
    if p95_ms > thresholds.latency_p95_ms:
        return AlertCheck(
            fired=True,
            reason=f"p95 latency {p95_ms:.1f}ms exceeds threshold {thresholds.latency_p95_ms:.1f}ms",
        )
    return AlertCheck(fired=False, reason="p95 latency within threshold")


def check_drift(max_distance: float, max_distance_query: str, thresholds: Thresholds) -> AlertCheck:
    if max_distance > thresholds.drift_distance:
        return AlertCheck(
            fired=True,
            reason=(
                f"query '{max_distance_query}' drifted {max_distance:.4f} cosine distance, "
                f"exceeds threshold {thresholds.drift_distance:.4f}"
            ),
        )
    return AlertCheck(fired=False, reason="drift within threshold")


def build_slack_payload(title: str, checks: list[AlertCheck]) -> dict:
    fired = [c for c in checks if c.fired]
    lines = [f"- {c.reason}" for c in fired]
    return {
        "text": f"vector-drift-watch: {title}",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*vector-drift-watch: {title}*"}},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines) or "no thresholds crossed"},
            },
        ],
    }


def fire_alert(webhook_url: str, payload: dict, timeout_seconds: float = 5.0) -> bool:
    try:
        response = requests.post(webhook_url, json=payload, timeout=timeout_seconds)
        return response.ok
    except requests.RequestException:
        return False
