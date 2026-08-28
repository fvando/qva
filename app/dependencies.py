"""Dependências partilhadas da aplicação (singletons por processo).

Centraliza a construção de objetos com estado (câmera, cliente LLM, ...) para
que os routers os recebam via `Depends(...)` em vez de os criarem à mão.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.camera.base import CameraSource
from app.camera.factory import build_camera
from app.config import get_settings
from app.llm.base import LLMClient
from app.llm.http_client import HttpLLMClient
from app.llm.solver import QuestionSolver
from app.history import HistoryStore
from app.services.captures import CaptureRegistry
from app.services.metrics import MetricsCollector
from app.services.pipeline import QuestionPipeline
from app.vision.extractor import QuestionExtractor
from app.vision.processor import ImageProcessor
from app.websocket_manager import WebSocketManager


@lru_cache
def get_camera() -> CameraSource:
    """Instância única de `CameraSource` para o processo.

    Uma webcam USB é um recurso exclusivo — abrir várias `VideoCapture` sobre o
    mesmo dispositivo falha. Manter uma só instância evita isso.
    """
    return build_camera(get_settings())


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
def get_llm_client() -> LLMClient:
    """Cliente LLM único do processo (mantém o `httpx.AsyncClient` vivo)."""
    return HttpLLMClient(get_settings())


def get_question_extractor(
    llm: LLMClient = Depends(get_llm_client),
) -> QuestionExtractor:
    return QuestionExtractor(llm=llm, settings=get_settings())


def get_solver(llm: LLMClient = Depends(get_llm_client)) -> QuestionSolver:
    return QuestionSolver(llm=llm)


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
