"""TASK-002 — USBCamera (sem exigir webcam física)."""

import numpy as np
import pytest

from app.camera.base import CameraError
from app.camera.usb import USBCamera, _parse_device


def test_parse_device_index_vs_path():
    assert _parse_device("0") == 0
    assert _parse_device("2") == 2
    assert _parse_device("/dev/video1") == "/dev/video1"


def test_capture_before_open_raises():
    cam = USBCamera("0")
    with pytest.raises(CameraError):
        cam.capture()


def test_close_is_idempotent():
    cam = USBCamera("0")
    cam.close()
    cam.close()  # não deve rebentar


def test_open_failure_raises_camera_error(monkeypatch):
    class FakeCap:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr("app.camera.usb.cv2.VideoCapture", lambda dev: FakeCap())
    with pytest.raises(CameraError):
        USBCamera("0").open()


def test_is_available_false_when_device_absent(monkeypatch):
    class FakeCap:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr("app.camera.usb.cv2.VideoCapture", lambda dev: FakeCap())
    assert USBCamera("0").is_available() is False


def test_capture_returns_frame_with_fake_backend(monkeypatch):
    frame = np.zeros((4, 4, 3), dtype=np.uint8)

    class FakeCap:
        def __init__(self):
            self._open = True

        def isOpened(self):
            return self._open

        def read(self):
            return True, frame.copy()

        def release(self):
            self._open = False

    monkeypatch.setattr("app.camera.usb.cv2.VideoCapture", lambda dev: FakeCap())
    cam = USBCamera("0")
    cam.open()
    out = cam.capture()
    assert out.shape == (4, 4, 3)
    assert cam.is_available() is True
    cam.close()
