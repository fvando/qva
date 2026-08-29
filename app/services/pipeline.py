"""`QuestionPipeline` — orquestração central (TASK-009).

Concentra todo o fluxo. Nenhuma lógica de negócio vive nos endpoints:

    frame     = camera.capture()
    processed = image_processor.process(frame)
    question  = extractor.extract(processed)
    result    = solver.solve(question)
    websocket_manager.broadcast(...)
    return ConsolidatedResponse(...)

Garantias:
  - As operações pesadas de OpenCV correm em `asyncio.to_thread` (não bloqueiam
    o event loop do FastAPI).
  - Cada passo é instrumentado com `time.perf_counter()` -> `Timing`.
  - Estados (`CaptureState`) e eventos WebSocket são emitidos em cada transição.
  - O pipeline **nunca** propaga exceção: qualquer falha vira uma
    `ConsolidatedResponse(status="error")` com um motivo estável.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from contextlib import contextmanager

from app.camera.base import CameraError, CameraSource
from app.history import HistoryStore
from app.models.result import ConsolidatedResponse, Timing
from app.services.captures import CaptureRegistry, CaptureState
from app.services.metrics import MetricsCollector
from app.vision.extractor import QuestionExtractionError, QuestionExtractor
from app.vision.processor import ImageProcessor, ImageQualityError
from app.llm.solver import QuestionSolveError, QuestionSolver
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
        metrics: MetricsCollector | None = None,
        history: HistoryStore | None = None,
    ) -> None:
        self._camera = camera
        self._image_processor = image_processor
        self._extractor = extractor
        self._solver = solver
        self._registry = registry
        self._ws = websocket_manager
        self._metrics = metrics
        self._history = history

    # -- eventos ---------------------------------------------------------
    async def _emit(self, event: str, data: dict | None = None) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.broadcast(event, data or {})
        except NotImplementedError:
            pass  # WebSocketManager completo chega na TASK-010

    # -- fluxo principal ------------------------------------------------
    async def process_capture(
        self, capture_id: str, *, frame=None
    ) -> ConsolidatedResponse:
        """Executa o pipeline para uma captura já registada no `CaptureRegistry`.

        Se `frame` for dado (captura automática, TASK-016), usa-o em vez de ler
        de novo da câmera — assim não se perde o instante estável observado.
        """
        timing = Timing()
        overall = time.perf_counter()
        log_extra = {"capture_id": capture_id, "request_id": capture_id}

        logger.info("CAPTURE_STARTED", extra=log_extra)
        await self._emit("capture_started", {"capture_id": capture_id})

        try:
            # 1. Captura do frame -----------------------------------------
            self._registry.set_state(capture_id, CaptureState.CAPTURING)
            with _step(timing, "capture_ms"):
                if frame is None:
                    frame = await asyncio.to_thread(self._capture_frame)
            # hash curto do frame — para confirmar nos logs que cada captura usa
            # uma imagem diferente (diagnóstico de "resposta de imagem antiga").
            fp = hashlib.sha1(frame.tobytes()).hexdigest()[:12] if frame is not None else "none"
            logger.info("CAPTURE_COMPLETED", extra={**log_extra, "frame": fp})

            # 2. Processamento de imagem (OpenCV -> thread) -------------
            self._registry.set_state(capture_id, CaptureState.PROCESSING_IMAGE)
            with _step(timing, "image_processing_ms"):
                processed = await asyncio.to_thread(
                    self._image_processor.process_sync, frame
                )
            logger.info(
                "IMAGE_PROCESSED",
                extra={**log_extra, **processed.metrics(), "screen": processed.screen_detected},
            )

            combined = getattr(self._extractor, "supports_combined", False)

            if combined:
                # Modo B: extração + resolução numa só chamada ao LLM.
                self._registry.set_state(capture_id, CaptureState.EXTRACTING_QUESTION)
                logger.info("LLM_REQUEST_STARTED", extra=log_extra)
                with _step(timing, "question_extraction_ms"):
                    question, result = await self._extractor.extract_and_solve(processed)
                logger.info(
                    "QUESTION_EXTRACTED", extra={**log_extra, "type": question.type.value}
                )
                logger.info("LLM_REQUEST_COMPLETED", extra=log_extra)
                await self._emit(
                    "question_detected",
                    {"capture_id": capture_id, "question": question.model_dump(mode="json")},
                )
            else:
                # 3. Extração da questão --------------------------------
                self._registry.set_state(capture_id, CaptureState.EXTRACTING_QUESTION)
                with _step(timing, "question_extraction_ms"):
                    question = await self._extractor.extract(processed)
                logger.info(
                    "QUESTION_EXTRACTED", extra={**log_extra, "type": question.type.value}
                )
                await self._emit(
                    "question_detected",
                    {"capture_id": capture_id, "question": question.model_dump(mode="json")},
                )

                # 4. Resolução -------------------------------------
                self._registry.set_state(capture_id, CaptureState.SOLVING)
                logger.info("LLM_REQUEST_STARTED", extra=log_extra)
                with _step(timing, "llm_ms"):
                    result = await self._solver.solve(question)
                logger.info("LLM_REQUEST_COMPLETED", extra=log_extra)

            timing.total_ms = (time.perf_counter() - overall) * 1000
            response = ConsolidatedResponse(
                id=capture_id,
                status="completed",
                question=question,
                result=result,
                timing=timing,
            )
            self._registry.complete(capture_id, response)
            if self._metrics is not None:
                self._metrics.record(timing, ok=True)
            if self._history is not None:
                self._history.save(response)
            logger.info("ANSWER_READY", extra={**log_extra, "latency_ms": round(timing.total_ms, 1)})
            await self._emit(
                "answer_ready",
                {"capture_id": capture_id, "response": response.model_dump(mode="json")},
            )
            return response

        except Exception as exc:  # noqa: BLE001 - o pipeline nunca deve rebentar
            timing.total_ms = (time.perf_counter() - overall) * 1000
            reason = _error_reason(exc)
            logger.warning(
                "PIPELINE_ERROR",
                extra={**log_extra, "error_type": type(exc).__name__},
            )
            response = ConsolidatedResponse(
                id=capture_id, status="error", timing=timing, error=reason
            )
            self._registry.fail(capture_id, reason)
            if self._metrics is not None:
                self._metrics.record(timing, ok=False)
            await self._emit("error", {"capture_id": capture_id, "reason": reason})
            return response

    def _capture_frame(self):
        self._camera.open()
        return self._camera.capture()


@contextmanager
def _step(timing: Timing, field: str):
    """Mede o tempo de um passo e escreve-o no campo indicado de `Timing`."""
    start = time.perf_counter()
    try:
        yield
    finally:
        setattr(timing, field, (time.perf_counter() - start) * 1000)


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
