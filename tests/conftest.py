"""Fixtures partilhadas dos testes."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.camera.base import CameraSource
from app import dependencies
from app.dependencies import get_camera
from app.main import create_app


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Limpa os singletons `@lru_cache` entre testes (registry de capturas,
    câmera, etc.) para não haver contaminação de estado."""
    for fn in (
        dependencies.get_camera,
        dependencies.get_capture_registry,
        dependencies.get_websocket_manager,
        dependencies.get_image_processor,
        dependencies.get_question_extractor,
    ):
        fn.cache_clear()
    yield


class FakeCamera(CameraSource):
    """Câmera de teste: devolve sempre a mesma imagem, sem hardware."""

    def __init__(self, available: bool = True) -> None:
        self._available = available
        self.opened = False

    def open(self) -> None:
        self.opened = True

    def capture(self) -> np.ndarray:
        return np.zeros((8, 8, 3), dtype=np.uint8)

    def close(self) -> None:
        self.opened = False

    def is_available(self) -> bool:
        return self._available


@pytest.fixture
def fake_camera() -> FakeCamera:
    return FakeCamera()


@pytest.fixture
def client(fake_camera: FakeCamera) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_camera] = lambda: fake_camera
    return TestClient(app)
