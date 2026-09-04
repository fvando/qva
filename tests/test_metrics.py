"""TASK-013 — métricas de latência agregadas."""

from app.models.result import Timing
from app.services.metrics import MetricsCollector, _percentile


def test_percentile_basic():
    vals = [10, 20, 30, 40, 50]
    assert _percentile(vals, 0.0) == 10
    assert _percentile(vals, 1.0) == 50
    assert _percentile(vals, 0.5) == 30


def test_percentile_empty():
    assert _percentile([], 0.95) == 0.0


def test_collector_counts_and_rates():
    m = MetricsCollector()
    m.record(Timing(total_ms=100, llm_ms=60), ok=True)
    m.record(Timing(total_ms=200, llm_ms=120), ok=True)
    m.record(Timing(total_ms=50), ok=False)

    snap = m.snapshot()
    assert snap["captures_total"] == 3
    assert snap["captures_completed"] == 2
    assert snap["captures_error"] == 1
    assert snap["success_rate"] == round(2 / 3, 3)
    assert snap["steps_ms"]["total_ms"]["count"] == 3
    assert snap["steps_ms"]["total_ms"]["avg_ms"] == round((100 + 200 + 50) / 3, 1)


def test_collector_window_is_bounded():
    m = MetricsCollector()
    for i in range(500):
        m.record(Timing(total_ms=float(i)), ok=True)
    snap = m.snapshot()
    assert snap["captures_total"] == 500  # contador não trunca
    assert snap["steps_ms"]["total_ms"]["count"] == snap["window"]  # amostras sim


def test_reset():
    m = MetricsCollector()
    m.record(Timing(total_ms=10), ok=True)
    m.reset()
    assert m.snapshot()["captures_total"] == 0


def test_empty_snapshot():
    snap = MetricsCollector().snapshot()
    assert snap["captures_total"] == 0
    assert snap["success_rate"] is None


# -- endpoint + integração com o pipeline ---------------------------
def test_metrics_endpoint_reflects_captures(client):
    assert client.get("/api/metrics").json()["captures_total"] == 0

    client.post("/api/capture")  # corre o pipeline (FakeCamera + FakeLLM)

    snap = client.get("/api/metrics").json()
    assert snap["captures_total"] == 1
    assert snap["captures_completed"] == 1
    assert snap["steps_ms"]["llm_ms"]["count"] == 1
