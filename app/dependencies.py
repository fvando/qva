"""Dependências partilhadas da aplicação (singletons por processo).

Centraliza a construção de objetos com estado (câmera, cliente LLM, ...) para
que os routers os recebam via `Depends(...)` em vez de os criarem à mão.
"""

from __future__ import annotations

from functools import lru_cache

from app.camera.base import CameraSource
from app.camera.factory import build_camera
from app.config import get_settings


@lru_cache
def get_camera() -> CameraSource:
    """Instância única de `CameraSource` para o processo.

    Uma webcam USB é um recurso exclusivo — abrir várias `VideoCapture` sobre o
    mesmo dispositivo falha. Manter uma só instância evita isso.
    """
    return build_camera(get_settings())
