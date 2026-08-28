"""`QuestionPipeline` — orquestração central (TASK-004; completado em TASK-009).

Concentra todo o fluxo. Nenhuma lógica de negócio deve viver nos endpoints:

    frame     = camera.capture()
    processed = await image_processor.process(frame)
    question  = await question_extractor.extract(processed)
    result    = await solver.solve(question)
    await websocket_manager.broadcast(result)
    return result

Nesta task o fluxo já existe e emite eventos/estados; os passos de visão e LLM
ainda são esqueletos (TASK-005/007/008), por isso o pipeline apanha
`NotImplementedError` e devolve uma resposta de erro em vez de rebentar — assim
`POST /api/capture` pode ser testado ponta a ponta desde já.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.camera.base import CameraError, CameraSource
from app.llm.solver import QuestionSolveError, QuestionSolver
from app.vision.extractor import QuestionExtractionError
from app.models.result import ConsolidatedResponse, Timing
from app.services.captures import CaptureRegistry, CaptureState
from app.vision.extractor import QuestionExtractor
from app.vision.processor import ImageProcessor, ImageQualityError
from app.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class QuestionPipeline:
    def __init__(
        self,
        camera: CameraSource,
        image_processor: ImageProcessor,
        extractor: QuestionExtractor,
        solver: QuestionSolver,
        registry: CaptureRegistry,
        websocket_manager: WebSocketManager | None = None,
    ) -> None:
        self._camera = camera
        self._image_processor = image_processor
        self._extractor = extractor
        self._solver = solver
        self._registry = registry
        self._ws = websocket_manager

    async def _emit(self, event: str, data: dict | None = None) -> None:
        if self._ws is not None:
            try:
                await self._ws.broadcast(event, data or {})
            except NotImplementedError:
                pass  # WebSocketManager chega na TASK-010

    async def process_capture(self, capture_id: str) -> ConsolidatedResponse:
        """Executa o pipeline para uma captura já registada."""
        t0 = time.perf_counter()
        timing = Timing()
        await self._emit("capture_started", {"capture_id": capture_id})

        try:
            # 1. Captura ------------------------------------------------------
            self._registry.set_state(capture_id, CaptureState.CAPTURING)
            t = time.perf_counter()
            frame = await asyncio.to_thread(self._capture_frame)
            timing.capture_ms = (time.perf_counter() - t) * 1000

            # 2. Processamento de imagem -----------------------------------
            self._registry.set_state(capture_id, CaptureState.PROCESSING_IMAGE)
            t = time.perf_counter()
            processed = await self._image_processor.process(frame)
            timing.image_processing_ms = (time.perf_counter() - t) * 1000

            # 3. Extração da questão -------------------------------------
            self._registry.set_state(capture_id, CaptureState.EXTRACTING_QUESTION)
            t = time.perf_counter()
            question = await self._extractor.extract(processed)
            timing.question_extraction_ms = (time.perf_counter() - t) * 1000
            await self._emit(
                "question_detected", {"capture_id": capture_id, "question": question.model_dump()}
            )

            # 4. Resolução ------------------------------------------------
            self._registry.set_state(capture_id, CaptureState.SOLVING)
            t = time.perf_counter()
            result = await self._solver.solve(question)
            timing.llm_ms = (time.perf_counter() - t) * 1000

            timing.total_ms = (time.perf_counter() - t0) * 1000
            response = ConsolidatedResponse(
                id=capture_id,
                status="completed",
                question=question,
                result=result,
                timing=timing,
            )
            self._registry.complete(capture_id, response)
            await self._emit("answer_ready", {"capture_id": capture_id, "response": response.model_dump()})
            return response

        except Exception as exc:  # noqa: BLE001 - o pipeline nunca deve rebentar
            timing.total_ms = (time.perf_counter() - t0) * 1000
            reason = _error_reason(exc)
            logger.warning(
                "PIPELINE_ERROR", extra={"capture_id": capture_id, "error_type": type(exc).__name__}
            )
            response = ConsolidatedResponse(
                id=capture_id, status="error", timing=timing, error=reason
            )
            self._registry.fail(capture_id, reason)
            await self._emit("error", {"capture_id": capture_id, "reason": reason})
            return response

    def _capture_frame(self):
        self._camera.open()
        return self._camera.capture()


def _error_reason(exc: BaseException) -> str:
    if isinstance(exc, ImageQualityError):
        return f"image_quality_error: {exc.reason}"
    if isinstance(exc, CameraError):
        return f"camera_error: {exc}"
    if isinstance(exc, QuestionExtractionError):
        return f"question_extraction_error: {exc}"
    if isinstance(exc, QuestionSolveError):
        return f"question_solve_error: {exc}"
    if isinstance(exc, NotImplementedError):
        return f"not_implemented: {exc}"
    return f"pipeline_error: {exc}"
