"""TASK-001 — a aplicação arranca e os endpoints base respondem."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_llm_status_reports_config():
    r = client.get("/api/llm/status")
    assert r.status_code == 200
    body = r.json()
    assert "configured_url" in body
    assert body["reachable"] is None  # TASK-006 liga a verificação real


def test_camera_status():
    r = client.get("/api/camera/status")
    assert r.status_code == 200
    assert r.json()["type"] == "usb"


def test_capture_not_yet_implemented():
    assert client.post("/api/capture").status_code == 501
