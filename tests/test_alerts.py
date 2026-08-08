from unittest.mock import patch

from vector_drift_watch.alerts import (
    Thresholds,
    build_slack_payload,
    check_drift,
    check_latency,
    fire_alert,
)


def test_check_latency_fires_when_over_threshold():
    result = check_latency(120.0, Thresholds(latency_p95_ms=50.0, drift_distance=0))
    assert result.fired is True
    assert "120.0" in result.reason


def test_check_latency_does_not_fire_when_within_threshold():
    result = check_latency(20.0, Thresholds(latency_p95_ms=50.0, drift_distance=0))
    assert result.fired is False


def test_check_drift_fires_when_over_threshold():
    result = check_drift(0.5, "some query", Thresholds(latency_p95_ms=0, drift_distance=0.15))
    assert result.fired is True
    assert "some query" in result.reason


def test_check_drift_does_not_fire_when_within_threshold():
    result = check_drift(0.02, "some query", Thresholds(latency_p95_ms=0, drift_distance=0.15))
    assert result.fired is False


def test_build_slack_payload_shape():
    checks = [check_latency(120.0, Thresholds(50.0, 0))]
    payload = build_slack_payload("test cycle", checks)
    assert payload["text"].startswith("vector-drift-watch:")
    assert isinstance(payload["blocks"], list)
    assert "120.0" in payload["blocks"][1]["text"]["text"]


def test_build_slack_payload_no_fired_checks_says_no_thresholds_crossed():
    checks = [check_latency(10.0, Thresholds(50.0, 0))]
    payload = build_slack_payload("test cycle", checks)
    assert "no thresholds crossed" in payload["blocks"][1]["text"]["text"]


def test_fire_alert_returns_true_on_2xx():
    with patch("vector_drift_watch.alerts.requests.post") as mock_post:
        mock_post.return_value.ok = True
        assert fire_alert("http://example.invalid/webhook", {"text": "hi"}) is True


def test_fire_alert_returns_false_on_request_exception():
    import requests

    with patch("vector_drift_watch.alerts.requests.post", side_effect=requests.ConnectionError("nope")):
        assert fire_alert("http://example.invalid/webhook", {"text": "hi"}) is False
