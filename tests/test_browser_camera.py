"""Câmera do browser: BrowserCamera + /api/camera/upload-frame."""

import time

import cv2
import numpy as np
import pytest

from app.camera.base import CameraError
from app.camera.browser import BrowserCamera


def _jpeg(color=(200, 200, 200)) -> bytes:
    img = np.full((60, 80, 3), color, dtype=np.uint8)
    return cv2.imencode(".jpg", img)[1].tobytes()


def test_not_available_before_any_frame():
    cam = BrowserCamera()
    assert cam.is_available() is False
    with pytest.raises(CameraError):
        cam.capture()


def test_set_and_capture_frame():
    cam = BrowserCamera()
    cam.set_frame_jpeg(_jpeg())
    assert cam.is_available() is True
    frame = cam.capture()
    assert frame.shape == (60, 80, 3)


def test_capture_returns_independent_copy():
    cam = BrowserCamera()
    cam.set_frame_jpeg(_jpeg())
    a = cam.capture()
    a[0, 0] = [0, 0, 0]
    assert not np.array_equal(cam.capture()[0, 0], a[0, 0])


def test_invalid_jpeg_raises():
    cam = BrowserCamera()
    with pytest.raises(CameraError):
        cam.set_frame_jpeg(b"isto nao e um jpeg")


def test_stale_frame_is_rejected(monkeypatch):
    cam = BrowserCamera()
    cam.set_frame_jpeg(_jpeg())
    base = time.monotonic()
    # simula passagem de tempo além do TTL (valor fixo, sem recursão)
    monkeypatch.setattr("app.camera.browser.time.monotonic", lambda: base + 999)
    assert cam.is_available() is False
    with pytest.raises(CameraError):
        cam.capture()


def test_close_clears_frame():
    cam = BrowserCamera()
    cam.set_frame_jpeg(_jpeg())
    cam.close()
    assert cam.is_available() is False


# -- endpoint ----------------------------------------------------------
def test_upload_frame_flow(client, fake_camera):
    r = client.post(
        "/api/camera/upload-frame",
        content=_jpeg(),
        headers={"Content-Type": "image/jpeg"},
    )
    assert r.status_code == 200
    assert r.json()["bytes"] > 0
    # o frame ficou disponível na browser_camera do manager
    assert fake_camera.browser_camera.is_available() is True


def test_upload_frame_empty_body(client):
    r = client.post(
        "/api/camera/upload-frame", content=b"", headers={"Content-Type": "image/jpeg"}
    )
    assert r.status_code == 400


def test_upload_frame_invalid_jpeg(client):
    r = client.post(
        "/api/camera/upload-frame", content=b"xxxx", headers={"Content-Type": "image/jpeg"}
    )
    assert r.status_code == 400


def test_select_browser_via_endpoint(client):
    r = client.post("/api/camera/select", json={"kind": "browser"})
    assert r.status_code == 200
    assert r.json()["active"]["type"] == "browser"
