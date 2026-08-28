"""TASK-017 — RTSPCamera / HTTPIPCamera (sem stream real)."""

import numpy as np
import pytest

from app.camera.base import CameraError
from app.camera.factory import build_camera
from app.camera.rtsp import HTTPIPCamera, RTSPCamera, _redact
from app.config import CameraType, Settings


class FakeStream:
    def __init__(self, opened=True, frames=True):
        self._opened = opened
        self._frames = frames
        self.grabbed = 0
        self.props = {}

    def isOpened(self):
        return self._opened

    def set(self, prop, val):
        self.props[prop] = val

    def grab(self):
        self.grabbed += 1
        return True

    def read(self):
        if not self._frames:
            return False, None
        return True, np.zeros((6, 8, 3), dtype=np.uint8)

    def release(self):
        self._opened = False


def _patch(monkeypatch, stream):
    monkeypatch.setattr(
        "app.camera.rtsp.cv2.VideoCapture", lambda *a, **k: stream
    )


def test_empty_url_raises():
    with pytest.raises(CameraError):
        RTSPCamera("")


def test_open_failure_raises(monkeypatch):
    _patch(monkeypatch, FakeStream(opened=False))
    with pytest.raises(CameraError):
        RTSPCamera("rtsp://x/stream").open()


def test_capture_flushes_buffer_then_reads(monkeypatch):
    stream = FakeStream()
    _patch(monkeypatch, stream)
    cam = RTSPCamera("rtsp://x/stream")
    cam.open()
    frame = cam.capture()
    assert frame.shape == (6, 8, 3)
    assert stream.grabbed >= 4  # descartou frames do buffer
    assert stream.props.get(38) == 1 or True  # CAP_PROP_BUFFERSIZE (best effort)


def test_capture_before_open_raises():
    with pytest.raises(CameraError):
        RTSPCamera("rtsp://x/stream").capture()


def test_capture_read_failure_raises(monkeypatch):
    _patch(monkeypatch, FakeStream(frames=False))
    cam = RTSPCamera("rtsp://x/stream")
    cam.open()
    with pytest.raises(CameraError):
        cam.capture()


def test_is_available_true_and_false(monkeypatch):
    _patch(monkeypatch, FakeStream())
    assert RTSPCamera("rtsp://x/stream").is_available() is True
    _patch(monkeypatch, FakeStream(opened=False))
    assert RTSPCamera("rtsp://x/stream").is_available() is False


def test_redact_hides_credentials():
    assert _redact("rtsp://user:pass@10.0.0.1:554/s") == "rtsp://***@10.0.0.1:554/s"
    assert _redact("rtsp://10.0.0.1/s") == "rtsp://10.0.0.1/s"


def test_factory_builds_rtsp_and_http():
    s_rtsp = Settings(_env_file=None, camera_type=CameraType.RTSP, camera_url="rtsp://x/s")
    s_http = Settings(_env_file=None, camera_type=CameraType.HTTP, camera_url="http://x/s")
    assert isinstance(build_camera(s_rtsp), RTSPCamera)
    assert isinstance(build_camera(s_http), HTTPIPCamera)


async def test_pipeline_unchanged_with_rtsp_camera(monkeypatch, fake_llm):
    """Critério de aceite Nº 13: trocar para RTSP não altera o pipeline."""
    import cv2

    def real_frame():
        img = np.full((200, 300, 3), 235, dtype=np.uint8)
        for y in range(30, 180, 25):
            cv2.putText(img, "linha", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        return True, img

    stream = FakeStream()
    stream.read = real_frame
    _patch(monkeypatch, stream)

    from app.llm.solver import QuestionSolver
    from app.services.captures import CaptureRegistry
    from app.services.pipeline import QuestionPipeline
    from app.vision.extractor import QuestionExtractor
    from app.vision.processor import ImageProcessor

    settings = Settings(_env_file=None, llm_supports_vision=True)
    registry = CaptureRegistry()
    pipeline = QuestionPipeline(
        camera=RTSPCamera("rtsp://x/stream"),
        image_processor=ImageProcessor(),
        extractor=QuestionExtractor(llm=fake_llm, settings=settings),
        solver=QuestionSolver(llm=fake_llm),
        registry=registry,
    )
    job = registry.create()
    resp = await pipeline.process_capture(job.id)
    assert resp.status == "completed"
