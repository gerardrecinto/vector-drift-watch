from vector_drift_watch.prober import percentile, probe_latency


def test_percentile_empty_list():
    assert percentile([], 50) == 0.0


def test_percentile_single_value():
    assert percentile([5.0], 99) == 5.0


def test_percentile_p50_of_evenly_spaced_values():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(values, 50) == 30.0


def test_percentile_p99_is_near_the_max():
    values = list(range(1, 101))  # 1..100
    values_f = [float(v) for v in values]
    assert percentile(values_f, 99) >= 98.0


def test_probe_latency_uses_injected_clock_and_counts_all_samples():
    fake_time = {"t": 0.0}

    def clock():
        return fake_time["t"]

    durations = iter([0.0, 0.01, 0.01, 0.03, 0.03, 0.10])

    def advancing_clock():
        fake_time["t"] += next(durations, 0.0)
        return fake_time["t"]

    queries = ["q1", "q2", "q3"]
    calls = []

    def query_fn(q):
        calls.append(q)

    report = probe_latency(queries, query_fn, repeats=1, clock=advancing_clock)

    assert report.sample_count == 3
    assert calls == queries
    assert report.p50_ms >= 0.0
    assert report.max_ms >= report.p95_ms >= report.p50_ms


def test_probe_latency_repeats_multiplies_sample_count():
    queries = ["q1", "q2"]
    report = probe_latency(queries, lambda q: None, repeats=5)
    assert report.sample_count == 10
