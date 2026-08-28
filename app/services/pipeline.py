"""`QuestionPipeline` — placeholder da TASK-001, implementado na TASK-009.

Concentra toda a orquestração:

    frame     = camera.capture()
    processed = await image_processor.process(frame)
    question  = await question_extractor.extract(processed)
    result    = await solver.solve(question)
    await websocket_manager.broadcast(result)
    return result

Nenhuma lógica de negócio deve viver nos endpoints FastAPI.
"""

from __future__ import annotations

from app.camera.base import CameraSource
from app.llm.solver import QuestionSolver
from app.models.result import ConsolidatedResponse
from app.vision.extractor import QuestionExtractor
from app.vision.processor import ImageProcessor


class QuestionPipeline:
    def __init__(
        self,
        camera: CameraSource,
        image_processor: ImageProcessor,
        extractor: QuestionExtractor,
        solver: QuestionSolver,
    ) -> None:
        self._camera = camera
        self._image_processor = image_processor
        self._extractor = extractor
        self._solver = solver

    async def process_capture(
        self,
    ) -> ConsolidatedResponse:  # pragma: no cover - TASK-009
        raise NotImplementedError("QuestionPipeline será implementado na TASK-009")
