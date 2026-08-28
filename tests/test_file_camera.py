"""TASK-012 — FileCamera e teste end-to-end com imagem fixture."""

from pathlib import Path

import numpy as np
import pytest

from app.camera.base import CameraError
from app.camera.factory import build_camera
from app.camera.file_camera import FileCamera
from app.config import CameraType, Settings

FIXTURE = Path(__file__).parent / "fixtures" / "question.jpg"


def test_fixture_exists():
    assert FIXTURE.is_file(), "correr: python tests/fixtures/make_fixture.py"


def test_capture_returns_bgr_frame():
    cam = FileCamera(str(FIXTURE))
    cam.open()
    frame = cam.capture()
    assert frame.ndim == 3 and frame.shape[2] == 3
    assert frame.dtype == np.uint8


def test_capture_returns_independent_copies():
    cam = FileCamera(str(FIXTURE))
    cam.open()
    a = cam.capture()
    a[0, 0] = [1, 2, 3]
    b = cam.capture()
    assert not np.array_equal(a[0, 0], b[0, 0])  # b não foi afetado


def test_missing_file_raises():
    cam = FileCamera("nao/existe.jpg")
    assert cam.is_available() is False
    with pytest.raises(CameraError):
        cam.open()


def test_capture_before_open_raises():
    with pytest.raises(CameraError):
        FileCamera(str(FIXTURE)).capture()


def test_factory_builds_file_camera():
    settings = Settings(
        _env_file=None, camera_type=CameraType.FILE, test_image=str(FIXTURE)
    )
    assert isinstance(build_camera(settings), FileCamera)


# -- end-to-end (secção 27/28): pipeline sem webcam ---------------------
async def test_pipeline_end_to_end_with_file_camera(fake_llm):
    """Câmera de ficheiro real + LLM fake -> ConsolidatedResponse completa."""
    from app.llm.solver import QuestionSolver
    from app.services.captures import CaptureRegistry
    from app.services.pipeline import QuestionPipeline
    from app.vision.extractor import QuestionExtractor
    from app.vision.processor import ImageProcessor

    settings = Settings(_env_file=None, llm_supports_vision=True)
    registry = CaptureRegistry()
    pipeline = QuestionPipeline(
        camera=FileCamera(str(FIXTURE)),
        image_processor=ImageProcessor(),
        extractor=QuestionExtractor(llm=fake_llm, settings=settings),
        solver=QuestionSolver(llm=fake_llm),
        registry=registry,
    )
    job = registry.create()
    resp = await pipeline.process_capture(job.id)

    assert resp.status == "completed"
    assert resp.question is not None
    assert resp.result is not None
    assert resp.timing.total_ms >= 0
    # a imagem passou pelo ImageProcessor real sem cair em image_quality_error
    assert resp.error is None
