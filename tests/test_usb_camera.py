"""TASK-002 — USBCamera (sem exigir webcam física)."""

import numpy as np
import pytest

from app.camera.base import CameraError
from app.camera.usb import USBCamera, _parse_device


def _bright(shape=(4, 4, 3)) -> np.ndarray:
    """Frame não-preto (passa a verificação de frame preto)."""
    return np.full(shape, 200, dtype=np.uint8)


class _FakeCap:
    """Backend falso: `read()` devolve `frames` em sequência, repetindo o último.
    `frames=None` -> nunca devolve frame (simula falha)."""

    def __init__(self, frames="bright", opened=True):
        self._opened = opened
        if frames == "bright":
            frames = [_bright()]
        elif frames == "black":
            frames = [np.zeros((4, 4, 3), dtype=np.uint8)]
        self._frames = frames
        self._i = 0

    def isOpened(self):
        return self._opened

    def grab(self):
        return True

    def read(self):
        if not self._frames:
            return False, None
        f = self._frames[min(self._i, len(self._frames) - 1)]
        self._i += 1
        return True, f.copy()

    def set(self, *a):
        pass

    def release(self):
        self._opened = False


def _patch(monkeypatch, factory):
    # a assinatura real é cv2.VideoCapture(device, backend)
    monkeypatch.setattr(
        "app.camera.usb.cv2.VideoCapture", lambda dev, backend=None: factory()
    )


def test_parse_device_index_vs_path():
    assert _parse_device("0") == 0
    assert _parse_device("2") == 2
    assert _parse_device("/dev/video1") == "/dev/video1"


def test_capture_before_open_raises():
    with pytest.raises(CameraError):
        USBCamera("0").capture()


def test_close_is_idempotent():
    cam = USBCamera("0")
    cam.close()
    cam.close()


def test_open_failure_raises_camera_error(monkeypatch):
    _patch(monkeypatch, lambda: _FakeCap(opened=False))
    with pytest.raises(CameraError):
        USBCamera("0").open()


def test_open_failure_when_never_reads_a_frame(monkeypatch):
    _patch(monkeypatch, lambda: _FakeCap(frames=None))
    with pytest.raises(CameraError):
        USBCamera("0").open()


def test_is_available_false_when_device_absent(monkeypatch):
    _patch(monkeypatch, lambda: _FakeCap(opened=False))
    assert USBCamera("0").is_available() is False


def test_capture_returns_frame(monkeypatch):
    _patch(monkeypatch, lambda: _FakeCap(frames="bright"))
    cam = USBCamera("0")
    cam.open()
    out = cam.capture()
    assert out.shape == (4, 4, 3)
    assert cam.is_available() is True
    cam.close()


def test_black_frame_raises_camera_error(monkeypatch):
    _patch(monkeypatch, lambda: _FakeCap(frames="black"))
    cam = USBCamera("0")
    # open() faz uma leitura de verificação — um frame preto não impede open,
    # mas capture() rejeita-o.
    cam._cap = _FakeCap(frames="black")
    with pytest.raises(CameraError):
        cam.capture()
