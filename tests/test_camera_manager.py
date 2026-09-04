"""Escolha de câmera em runtime — CameraManager + /api/camera/devices|select."""

import numpy as np
import pytest

from app.camera.base import CameraError
from app.camera.manager import CameraManager
from app.config import CameraType, Settings


class _FakeSource:
    def __init__(self, available=True):
        self._available = available
        self.closed = False

    def open(self):
        pass

    def capture(self):
        return np.zeros((4, 4, 3), dtype=np.uint8)

    def close(self):
        self.closed = True

    def is_available(self):
        return self._available


def _mgr(monkeypatch, initial_available=True):
    monkeypatch.setattr(
        "app.camera.manager.build_camera", lambda s: _FakeSource(initial_available)
    )
    return CameraManager(Settings(_env_file=None))


def test_description_reflects_initial_config(monkeypatch):
    monkeypatch.setattr("app.camera.manager.build_camera", lambda s: _FakeSource())
    m = CameraManager(Settings(_env_file=None, camera_type=CameraType.USB, camera_device="2"))
    assert m.description == {"type": "usb", "target": "2"}


def test_select_switches_and_closes_old(monkeypatch):
    m = _mgr(monkeypatch)
    old = m._active
    new_source = _FakeSource(available=True)
    monkeypatch.setattr("app.camera.manager._build", lambda k, t, s: new_source)

    desc = m.select("rtsp", "rtsp://x/stream")
    assert desc == {"type": "rtsp", "target": "rtsp://x/stream"}
    assert m._active is new_source
    assert old.closed is True


def test_select_rejects_unavailable_and_keeps_old(monkeypatch):
    m = _mgr(monkeypatch)
    old = m._active
    monkeypatch.setattr(
        "app.camera.manager._build", lambda k, t, s: _FakeSource(available=False)
    )
    with pytest.raises(CameraError):
        m.select("usb", "3")
    assert m._active is old  # não trocou
    assert old.closed is False


def test_is_available_result_is_cached(monkeypatch):
    """is_available() não deve sondar a câmera a cada chamada (só a cada
    _AVAILABILITY_CACHE_S) — evita abrir/fechar a webcam repetidamente."""
    m = _mgr(monkeypatch)
    calls = {"n": 0}

    def probe():
        calls["n"] += 1

    m._active.open = probe
    m._active.capture = lambda: None

    m.is_available()
    m.is_available()
    m.is_available()
    assert calls["n"] == 1  # só sondou uma vez (as outras vieram do cache)


def test_capture_marks_available_without_probing(monkeypatch):
    m = _mgr(monkeypatch)
    m._avail_ts = 0.0  # força cache expirado
    m.capture()
    # logo a seguir, is_available não volta a sondar
    m._active.open = lambda: (_ for _ in ()).throw(AssertionError("não devia sondar"))
    assert m.is_available() is True


def test_list_devices_uses_names_when_available(monkeypatch):
    m = _mgr(monkeypatch)
    monkeypatch.setattr(
        "app.camera.manager.list_video_input_names",
        lambda: ["Logi C270 HD WebCam", "HP 5MP Camera"],
    )
    devices = m.list_devices()
    assert [d["target"] for d in devices] == ["0", "1"]
    assert devices[0]["label"].startswith("Logi C270")
    assert devices[1]["label"].startswith("HP 5MP")


def test_list_devices_falls_back_to_probe(monkeypatch):
    m = _mgr(monkeypatch)
    monkeypatch.setattr("app.camera.manager.list_video_input_names", lambda: None)
    monkeypatch.setattr(
        "app.camera.manager.probe_device",
        lambda idx: "MSMF" if idx in (0, 1) else None,
    )
    devices = m.list_devices()
    assert [d["target"] for d in devices] == ["0", "1"]


# -- endpoints (via FakeCameraManager do conftest) --------------------
def test_devices_endpoint(client):
    r = client.get("/api/camera/devices")
    assert r.status_code == 200
    body = r.json()
    assert body["devices"][0]["target"] == "0"
    assert body["active"]["type"] == "usb"


def test_select_endpoint_ok(client):
    r = client.post("/api/camera/select", json={"kind": "rtsp", "target": "rtsp://x/s"})
    assert r.status_code == 200
    assert r.json()["active"] == {"type": "rtsp", "target": "rtsp://x/s"}
    # o status passa a refletir a nova câmera
    assert client.get("/api/camera/status").json()["type"] == "rtsp"


def test_select_endpoint_bad_request(client, fake_camera):
    def boom(k, t):
        raise CameraError("indisponível")

    fake_camera.select = boom
    r = client.post("/api/camera/select", json={"kind": "rtsp", "target": "rtsp://x"})
    assert r.status_code == 400
