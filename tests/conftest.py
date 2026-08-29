"""Fixtures partilhadas dos testes."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.camera.base import CameraSource
from app.config import Settings
from app.llm.base import LLMClient, LLMRequest, LLMResponse
from app import dependencies
from app.dependencies import get_camera, get_camera_manager, get_llm_client
from app.main import create_app


TEST_SETTINGS = Settings(
    _env_file=None, llm_supports_vision=False, llm_mode="ocr"
)

# Texto que a FakeCamera "mostra" e que o FakeLLM devolve — coerentes entre si
# para o caminho OCR passar os guards de correspondência.
_FAKE_QUESTION_TEXT = "Qual estrutura de dados segue a politica LIFO"
_FAKE_LLM_JSON = (
    '{"type":"multiple_choice","language":"pt",'
    f'"question":"{_FAKE_QUESTION_TEXT}",'
    '"options":{"A":"Fila","B":"Pilha"},"answer":"B","answer_text":"Pilha",'
    '"explanation":"LIFO e pilha","confidence":0.9}'
)


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    """Os testes nunca devem depender do `.env` real da máquina nem carregar
    os modelos ONNX do OCR."""
    for target in (
        "app.config.get_settings",
        "app.dependencies.get_settings",
        "app.main.get_settings",
    ):
        monkeypatch.setattr(target, lambda: TEST_SETTINGS)
    monkeypatch.setattr("app.dependencies.get_ocr_engine", lambda: _FakeOCR())
    yield


class _FakeOCR:
    """OCR de teste — texto coerente com o FakeLLM, sem carregar ONNX."""

    def image_to_text(self, image) -> str:  # noqa: ARG002
        return _FAKE_QUESTION_TEXT + " A) Fila B) Pilha C) Arvore D) Lista ligada"


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Limpa os singletons `@lru_cache` entre testes (registry de capturas,
    câmera, etc.) para não haver contaminação de estado."""
    for fn in (
        dependencies.get_camera_manager,
        dependencies.get_capture_registry,
        dependencies.get_websocket_manager,
        dependencies.get_image_processor,
        dependencies.get_llm_client,
        dependencies.get_vision_llm_client,
        dependencies.get_metrics,
        dependencies.get_history,
        dependencies.get_change_detector,
    ):
        fn.cache_clear()
    yield


class FakeLLM(LLMClient):
    """LLM de teste: devolve um texto fixo, sem rede."""

    def __init__(self, text: str = _FAKE_LLM_JSON, reachable: bool = True) -> None:
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
        lines = [
            "Qual estrutura de dados", "segue a politica LIFO?",
            "A) Fila", "B) Pilha", "C) Arvore", "D) Lista ligada",
        ]
        for i, t in enumerate(lines):
            cv2.putText(
                img, t, (20, 60 + i * 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2,
            )
        return img

    def close(self) -> None:
        self.opened = False

    def is_available(self) -> bool:
        return self._available


class FakeCameraManager(FakeCamera):
    """FakeCamera + a API de gestão do CameraManager (para os testes de client)."""

    def __init__(self) -> None:
        super().__init__()
        self._desc = {"type": "usb", "target": "0"}
        from app.camera.browser import BrowserCamera

        self.browser_camera = BrowserCamera()

    @property
    def description(self) -> dict:
        return dict(self._desc)

    def select(self, kind: str, target: str) -> dict:
        self._desc = {"type": kind, "target": target}
        return self.description

    def list_devices(self) -> list[dict]:
        return [{"kind": "usb", "target": "0", "label": "Câmera USB 0"}]


@pytest.fixture
def fake_camera() -> FakeCameraManager:
    return FakeCameraManager()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(fake_camera: FakeCamera, fake_llm: FakeLLM) -> TestClient:
    from app.config import get_settings as _real_get_settings

    app = create_app()
    app.dependency_overrides[get_camera] = lambda: fake_camera
    app.dependency_overrides[get_camera_manager] = lambda: fake_camera
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[_real_get_settings] = lambda: TEST_SETTINGS
    return TestClient(app)
