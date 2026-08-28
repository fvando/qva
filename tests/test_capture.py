"""TASK-004 — captura manual (fluxo assíncrono + capture_id)."""

from app.services.captures import CaptureRegistry, CaptureState


def test_registry_lifecycle():
    reg = CaptureRegistry()
    job = reg.create()
    assert reg.get(job.id) is job
    assert job.state is CaptureState.CAPTURING

    reg.set_state(job.id, CaptureState.SOLVING)
    assert reg.get(job.id).state is CaptureState.SOLVING

    reg.fail(job.id, "boom")
    assert reg.get(job.id).state is CaptureState.ERROR
    assert reg.get(job.id).error == "boom"


def test_registry_unknown_id_is_safe():
    reg = CaptureRegistry()
    assert reg.get("nope") is None
    reg.set_state("nope", CaptureState.SOLVING)  # não deve rebentar


def test_capture_returns_202_with_id(client):
    r = client.post("/api/capture")
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "processing"
    assert len(body["capture_id"]) == 36  # uuid4


def test_capture_runs_pipeline_and_reports_state(client):
    """O pipeline corre ponta a ponta e nunca rebenta. Com a FakeCamera a
    devolver um frame trivial (8x8 zeros), o ImageProcessor rejeita a imagem
    e o pipeline termina em `error` — mas de forma controlada e consultável."""
    capture_id = client.post("/api/capture").json()["capture_id"]
    # BackgroundTasks do TestClient corre de forma síncrona após a resposta.
    r = client.get(f"/api/capture/{capture_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == capture_id
    assert body["status"] == "error"
    assert body["error"]  # há sempre um motivo
    assert body["timing"]["total_ms"] >= 0


def test_capture_status_404_for_unknown():
    from tests.conftest import FakeCamera
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.dependencies import get_camera

    app = create_app()
    app.dependency_overrides[get_camera] = lambda: FakeCamera()
    c = TestClient(app)
    assert c.get("/api/capture/does-not-exist").status_code == 404
