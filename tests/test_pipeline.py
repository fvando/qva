"""TASK-009 — QuestionPipeline: orquestração, estados, eventos, erros."""

import numpy as np
import pytest

from app.models.question import Question, QuestionType
from app.models.result import SolveResult
from app.services.captures import CaptureRegistry, CaptureState
from app.services.pipeline import QuestionPipeline
from app.vision.processor import ImageQualityError, ProcessedImage
from tests.conftest import FakeCamera


class RecordingWS:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def broadcast(self, event: str, data: dict) -> None:
        self.events.append(event)


class StubProcessor:
    async def process(self, frame):  # não usado pelo pipeline (usa process_sync)
        raise AssertionError("pipeline deve usar process_sync")

    def process_sync(self, frame) -> ProcessedImage:
        return ProcessedImage(image=frame, sharpness_score=100.0, brightness_score=128.0)


class StubExtractor:
    def __init__(self, question: Question | None = None) -> None:
        self._q = question or Question(type=QuestionType.MULTIPLE_CHOICE, question="?")

    async def extract(self, processed) -> Question:
        return self._q


class StubSolver:
    def __init__(self, result: SolveResult | None = None) -> None:
        self._r = result or SolveResult(answer="D", answer_text="d", confidence=0.9)

    async def solve(self, question) -> SolveResult:
        return self._r


def _pipeline(**over) -> tuple[QuestionPipeline, CaptureRegistry, RecordingWS]:
    reg = CaptureRegistry()
    ws = RecordingWS()
    p = QuestionPipeline(
        camera=over.get("camera", FakeCamera()),
        image_processor=over.get("processor", StubProcessor()),
        extractor=over.get("extractor", StubExtractor()),
        solver=over.get("solver", StubSolver()),
        registry=reg,
        websocket_manager=ws,
    )
    return p, reg, ws


async def test_happy_path_produces_consolidated_response():
    p, reg, ws = _pipeline()
    job = reg.create()
    resp = await p.process_capture(job.id)

    assert resp.status == "completed"
    assert resp.question.type is QuestionType.MULTIPLE_CHOICE
    assert resp.result.answer == "D"
    # todos os passos medidos
    assert resp.timing.capture_ms >= 0
    assert resp.timing.image_processing_ms >= 0
    assert resp.timing.question_extraction_ms >= 0
    assert resp.timing.llm_ms >= 0
    assert resp.timing.total_ms >= 0
    assert reg.get(job.id).state is CaptureState.COMPLETED


async def test_emits_events_in_order():
    p, reg, ws = _pipeline()
    await p.process_capture(reg.create().id)
    assert ws.events == [
        "capture_started",
        "question_detected",
        "answer_ready",
    ]


async def test_image_quality_error_stops_pipeline():
    class BadProcessor(StubProcessor):
        def process_sync(self, frame):
            raise ImageQualityError("blur_detected")

    p, reg, ws = _pipeline(processor=BadProcessor())
    job = reg.create()
    resp = await p.process_capture(job.id)

    assert resp.status == "error"
    assert resp.error == "image_quality_error: blur_detected"
    assert resp.question is None
    assert resp.result is None
    assert reg.get(job.id).state is CaptureState.ERROR
    assert ws.events[-1] == "error"


async def test_camera_failure_is_reported():
    cam = FakeCamera()

    def boom():
        from app.camera.base import CameraError

        raise CameraError("desligada")

    cam.capture = boom
    p, reg, _ = _pipeline(camera=cam)
    resp = await p.process_capture(reg.create().id)
    assert resp.status == "error"
    assert "camera_error" in resp.error


async def test_solver_failure_is_reported():
    class BoomSolver:
        async def solve(self, question):
            from app.llm.solver import QuestionSolveError

            raise QuestionSolveError("LLM caiu")

    p, reg, _ = _pipeline(solver=BoomSolver())
    resp = await p.process_capture(reg.create().id)
    assert resp.status == "error"
    assert "question_solve_error" in resp.error


async def test_pipeline_works_without_websocket():
    reg = CaptureRegistry()
    p = QuestionPipeline(
        camera=FakeCamera(),
        image_processor=StubProcessor(),
        extractor=StubExtractor(),
        solver=StubSolver(),
        registry=reg,
        websocket_manager=None,
    )
    resp = await p.process_capture(reg.create().id)
    assert resp.status == "completed"
