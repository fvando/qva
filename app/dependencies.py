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
from app.llm.solver import QuestionSolver
from app.services.captures import CaptureRegistry
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
def get_image_processor() -> ImageProcessor:
    return ImageProcessor()


@lru_cache
def get_question_extractor() -> QuestionExtractor:
    return QuestionExtractor()


def get_solver() -> QuestionSolver:
    # O LLMClient concreto (HttpLLMClient) chega na TASK-006; até lá o solver
    # recebe None e o pipeline trata o NotImplementedError.
    return QuestionSolver(llm=None)  # type: ignore[arg-type]


def get_pipeline(
    camera: CameraSource = Depends(get_camera),
    image_processor: ImageProcessor = Depends(get_image_processor),
    extractor: QuestionExtractor = Depends(get_question_extractor),
    solver: QuestionSolver = Depends(get_solver),
    registry: CaptureRegistry = Depends(get_capture_registry),
    ws: WebSocketManager = Depends(get_websocket_manager),
) -> QuestionPipeline:
    return QuestionPipeline(
        camera=camera,
        image_processor=image_processor,
        extractor=extractor,
        solver=solver,
        registry=registry,
        websocket_manager=ws,
    )
