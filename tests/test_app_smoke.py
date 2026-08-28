"""TASK-001/002 — a aplicação arranca e os endpoints base respondem."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["camera"] is True  # FakeCamera disponível


def test_health_reports_camera_down(client, fake_camera):
    fake_camera._available = False
    assert client.get("/health").json()["camera"] is False


def test_llm_status_reports_config(client):
    r = client.get("/api/llm/status")
    assert r.status_code == 200
    body = r.json()
    assert "configured_url" in body
    assert body["reachable"] is None  # TASK-006 liga a verificação real


def test_camera_status(client):
    r = client.get("/api/camera/status")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "usb"
    assert body["available"] is True


def test_capture_accepts_and_returns_id(client):
    r = client.post("/api/capture")
    assert r.status_code == 202
    assert r.json()["status"] == "processing"
