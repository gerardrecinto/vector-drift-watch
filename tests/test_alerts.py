from unittest.mock import patch

from vector_drift_watch.alerts import (
    ConsecutiveBreachTracker,
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


def test_consecutive_breach_tracker_does_not_escalate_on_single_breach():
    tracker = ConsecutiveBreachTracker(required_streak=2)
    assert tracker.record("latency", fired=True) is False


def test_consecutive_breach_tracker_escalates_after_required_streak():
    tracker = ConsecutiveBreachTracker(required_streak=2)
    assert tracker.record("latency", fired=True) is False
    assert tracker.record("latency", fired=True) is True


def test_consecutive_breach_tracker_resets_streak_on_non_breach():
    tracker = ConsecutiveBreachTracker(required_streak=2)
    assert tracker.record("latency", fired=True) is False
    assert tracker.record("latency", fired=False) is False
    assert tracker.record("latency", fired=True) is False
    assert tracker.record("latency", fired=True) is True


def test_consecutive_breach_tracker_tracks_each_check_independently():
    tracker = ConsecutiveBreachTracker(required_streak=2)
    assert tracker.record("latency", fired=True) is False
    assert tracker.record("drift", fired=True) is False
    assert tracker.record("drift", fired=True) is True
    # latency streak is untouched by drift's escalation
    assert tracker.record("latency", fired=True) is True


def test_consecutive_breach_tracker_default_streak_is_two():
    tracker = ConsecutiveBreachTracker()
    assert tracker.record("latency", fired=True) is False
    assert tracker.record("latency", fired=True) is True
