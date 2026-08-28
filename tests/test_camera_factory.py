"""TASK-001 — a fábrica de câmera escolhe a classe certa pela config."""

import pytest

from app.camera.factory import build_camera
from app.camera.file_camera import FileCamera
from app.camera.usb import USBCamera
from app.config import CameraType, Settings


def test_builds_usb():
    cam = build_camera(Settings(_env_file=None, camera_type=CameraType.USB))
    assert isinstance(cam, USBCamera)


def test_builds_file():
    cam = build_camera(Settings(_env_file=None, camera_type=CameraType.FILE))
    assert isinstance(cam, FileCamera)


def test_rtsp_not_yet_supported():
    with pytest.raises(NotImplementedError):
        build_camera(Settings(_env_file=None, camera_type=CameraType.RTSP))
