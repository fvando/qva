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


def test_list_devices_probes_usb(monkeypatch):
    m = _mgr(monkeypatch)

    class Cap:
        def release(self):
            pass

    # só o índice 0 e 1 "respondem"
    monkeypatch.setattr(
        "app.camera.manager._open_any_backend",
        lambda idx: Cap() if idx in (0, 1) else None,
    )
    devices = m.list_devices()
    assert [d["target"] for d in devices] == ["0", "1"]
    assert all(d["kind"] == "usb" for d in devices)


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
