"""Fixtures partilhadas dos testes."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.camera.base import CameraSource
from app.llm.base import LLMClient, LLMRequest, LLMResponse
from app import dependencies
from app.dependencies import get_camera, get_llm_client
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
        dependencies.get_llm_client,
    ):
        fn.cache_clear()
    yield


class FakeLLM(LLMClient):
    """LLM de teste: devolve um texto fixo, sem rede."""

    def __init__(self, text: str = '{"answer":"D"}', reachable: bool = True) -> None:
        self._text = text
        self._reachable = reachable
        self.calls: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return LLMResponse(text=self._text, model="fake", latency_ms=1.0)

    async def health(self) -> bool:
        return self._reachable


class FakeCamera(CameraSource):
    """Câmera de teste: devolve sempre a mesma imagem, sem hardware."""

    def __init__(self, available: bool = True) -> None:
        self._available = available
        self.opened = False

    def open(self) -> None:
        self.opened = True

    def capture(self) -> np.ndarray:
        # Frame nítido e bem iluminado, com detalhe suficiente para passar as
        # verificações de qualidade do ImageProcessor (TASK-005).
        import cv2

        img = np.full((480, 640, 3), 235, dtype=np.uint8)
        for y in range(40, 440, 30):
            cv2.putText(
                img, "linha " + str(y), (30, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2,
            )
        return img

    def close(self) -> None:
        self.opened = False

    def is_available(self) -> bool:
        return self._available


@pytest.fixture
def fake_camera() -> FakeCamera:
    return FakeCamera()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(fake_camera: FakeCamera, fake_llm: FakeLLM) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_camera] = lambda: fake_camera
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    return TestClient(app)
