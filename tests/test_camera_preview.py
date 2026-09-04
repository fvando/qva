"""TASK-003 — preview (frame único) e stream MJPEG."""

import numpy as np
import pytest

from app.vision.encoding import encode_jpeg


def test_encode_jpeg_produces_valid_marker():
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    data = encode_jpeg(frame)
    assert data[:2] == b"\xff\xd8"  # SOI JPEG
    assert data[-2:] == b"\xff\xd9"  # EOI JPEG


def test_encode_jpeg_rejects_bad_input():
    with pytest.raises(ValueError):
        encode_jpeg(np.zeros((0, 0, 3), dtype=np.uint8))


def test_frame_endpoint_returns_jpeg(client):
    r = client.get("/api/camera/frame")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"


def test_frame_endpoint_503_when_camera_down(client, fake_camera):
    from app.camera.base import CameraError

    def boom():
        raise CameraError("sem câmera")

    fake_camera.capture = boom
    assert client.get("/api/camera/frame").status_code == 503


async def test_mjpeg_frames_generator_bounded(fake_camera):
    from app.api.camera import mjpeg_frames

    parts = [part async for part in mjpeg_frames(fake_camera, max_frames=2)]
    assert len(parts) == 2
    assert parts[0].startswith(b"--qvaframe")
    assert b"Content-Type: image/jpeg" in parts[0]
    assert b"\xff\xd8" in parts[0]  # JPEG embutido


async def test_mjpeg_frames_stops_when_camera_fails(fake_camera):
    from app.api.camera import mjpeg_frames
    from app.camera.base import CameraError

    def boom():
        raise CameraError("caiu")

    fake_camera.capture = boom
    parts = [part async for part in mjpeg_frames(fake_camera, max_frames=5)]
    assert parts == []
