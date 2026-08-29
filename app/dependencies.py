"""Dependências partilhadas da aplicação (singletons por processo).

Centraliza a construção de objetos com estado (câmera, cliente LLM, ...) para
que os routers os recebam via `Depends(...)` em vez de os criarem à mão.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.camera.base import CameraSource
from app.camera.manager import CameraManager
from app.config import get_settings
from app.llm.base import LLMClient
from app.llm.http_client import HttpLLMClient
from app.llm.solver import QuestionSolver
from app.history import HistoryStore
from app.services.captures import CaptureRegistry
from app.services.metrics import MetricsCollector
from app.services.pipeline import QuestionPipeline
from app.vision.change_detector import ChangeDetector
from app.vision.extractor import QuestionExtractor
from app.vision.processor import ImageProcessor
from app.websocket_manager import WebSocketManager


@lru_cache
def get_camera_manager() -> CameraManager:
    """Câmera ativa do processo, trocável em runtime pela UI.

    Uma webcam USB é um recurso exclusivo — manter uma só instância evita
    abrir várias `VideoCapture` sobre o mesmo dispositivo.
    """
    return CameraManager(get_settings())


def get_camera() -> CameraSource:
    """A `CameraSource` que o resto da app usa (é o `CameraManager`)."""
    return get_camera_manager()


@lru_cache
def get_capture_registry() -> CaptureRegistry:
    return CaptureRegistry()


@lru_cache
def get_websocket_manager() -> WebSocketManager:
    return WebSocketManager()


@lru_cache
def get_metrics() -> MetricsCollector:
    return MetricsCollector()


@lru_cache
def get_history() -> HistoryStore:
    return HistoryStore(enabled=get_settings().store_history)


@lru_cache
def get_image_processor() -> ImageProcessor:
    return ImageProcessor()


@lru_cache
def get_change_detector() -> ChangeDetector:
    return ChangeDetector(threshold=get_settings().change_threshold)


@lru_cache
def get_llm_client() -> LLMClient:
    """Cliente LLM (texto) único do processo."""
    return HttpLLMClient(get_settings())


@lru_cache
def get_vision_llm_client() -> LLMClient | None:
    """Cliente LLM de visão para `LLM_MODE=vision`/`hybrid`.

    Usa `LLM_VISION_BASE_URL`/`LLM_VISION_MODEL` se dados; senão, se o LLM
    principal já suporta visão, reutiliza esse; senão `None`."""
    s = get_settings()
    if s.llm_vision_base_url or s.llm_vision_model:
        vs = s.model_copy(
            update={
                "llm_base_url": s.llm_vision_base_url or s.llm_base_url,
                "llm_model": s.llm_vision_model or s.llm_model,
                "llm_supports_vision": True,
            }
        )
        return HttpLLMClient(vs)
    if s.llm_supports_vision:
        return get_llm_client()
    return None


@lru_cache
def get_ocr_engine():
    """Motor de OCR único do processo (modo B). Carrega os modelos ONNX uma
    vez — pré-aquecido no lifespan. `None` se nenhum motor disponível."""
    from app.vision.ocr import OCRUnavailableError, build_ocr_engine

    try:
        return build_ocr_engine()
    except OCRUnavailableError:
        return None


def get_question_extractor(
    llm: LLMClient = Depends(get_llm_client),
) -> QuestionExtractor:
    return QuestionExtractor(
        llm=llm,
        settings=get_settings(),
        ocr=get_ocr_engine(),
        vision_llm=get_vision_llm_client(),
    )


def get_solver(llm: LLMClient = Depends(get_llm_client)) -> QuestionSolver:
    return QuestionSolver(llm=llm)


def build_pipeline() -> QuestionPipeline:
    """Constrói o pipeline sem `Depends` — para uso fora de um request
    (lifespan, captura automática)."""
    settings = get_settings()
    llm = get_llm_client()
    return QuestionPipeline(
        camera=get_camera(),
        image_processor=get_image_processor(),
        extractor=QuestionExtractor(
            llm=llm,
            settings=settings,
            ocr=get_ocr_engine(),
            vision_llm=get_vision_llm_client(),
        ),
        solver=QuestionSolver(llm=llm),
        registry=get_capture_registry(),
        websocket_manager=get_websocket_manager(),
        metrics=get_metrics(),
        history=get_history(),
    )


def get_pipeline(
    camera: CameraSource = Depends(get_camera),
    image_processor: ImageProcessor = Depends(get_image_processor),
    extractor: QuestionExtractor = Depends(get_question_extractor),
    solver: QuestionSolver = Depends(get_solver),
    registry: CaptureRegistry = Depends(get_capture_registry),
    ws: WebSocketManager = Depends(get_websocket_manager),
    metrics: MetricsCollector = Depends(get_metrics),
    history: HistoryStore = Depends(get_history),
) -> QuestionPipeline:
    return QuestionPipeline(
        camera=camera,
        image_processor=image_processor,
        extractor=extractor,
        solver=solver,
        registry=registry,
        websocket_manager=ws,
        metrics=metrics,
        history=history,
    )
