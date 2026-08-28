"""Configuração central da aplicação (TASK-001).

Toda a configuração vem de variáveis de ambiente / ficheiro `.env`, seguindo o
princípio de não acoplar a aplicação a valores fixos no código nem a um
fornecedor específico de LLM. Nenhum outro módulo lê `os.environ` diretamente —
todos recebem um objeto `Settings` (injeção de dependência), o que torna os
testes triviais (basta construir um `Settings` com outros valores).
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CameraType(str, Enum):
    """Tipos de fonte de câmera suportados.

    `usb` e `file` funcionam no MVP; `rtsp`/`http` ficam preparados para a fase 2
    sem que o resto do pipeline precise de saber a diferença.
    """

    USB = "usb"
    FILE = "file"
    RTSP = "rtsp"
    HTTP = "http"


class Settings(BaseSettings):
    """Configuração validada da aplicação.

    Lida do ambiente e, em desenvolvimento, de um ficheiro `.env` na raiz.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Servidor -----------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    auth_token: str = ""
    """Token opcional. Vazio = sem autenticação (apenas LAN)."""

    # -- Câmera -----------------------------------------------------------
    camera_type: CameraType = CameraType.USB
    camera_device: str = "0"
    """Índice ou caminho do dispositivo para `CAMERA_TYPE=usb`."""
    camera_url: str = ""
    """URL para `CAMERA_TYPE=rtsp`/`http` (fase 2)."""
    test_image: str = "tests/fixtures/question.jpg"
    """Imagem usada por `CAMERA_TYPE=file` (desenvolvimento sem webcam)."""

    # -- Serviço LLM local ------------------------------------------------
    llm_base_url: str = "http://host.docker.internal:8001"
    llm_endpoint: str = "/v1/chat/completions"
    llm_model: str = "my-local-model"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 30.0
    llm_supports_vision: bool = True
    """Se o modelo local aceita imagens. O código de negócio não deve depender
    disto — a escolha entre modo multimodal e OCR+LLM é interna ao extractor."""

    # -- Deteção de mudança / captura automática ------------------------
    auto_capture_enabled: bool = False
    change_threshold: float = 0.25
    stabilization_ms: int = 800

    # -- Privacidade / histórico ----------------------------------------
    store_images: bool = False
    """Local-first: por omissão as imagens só existem em memória."""
    store_history: bool = True

    @property
    def llm_url(self) -> str:
        """URL completo do endpoint do LLM."""
        return f"{self.llm_base_url.rstrip('/')}/{self.llm_endpoint.lstrip('/')}"

    @property
    def auth_enabled(self) -> bool:
        return bool(self.auth_token)


@lru_cache
def get_settings() -> Settings:
    """Devolve a configuração (singleton em cache).

    Usar como dependência FastAPI: `settings: Settings = Depends(get_settings)`.
    Em testes, chamar `get_settings.cache_clear()` ou instanciar `Settings(...)`
    diretamente.
    """

    return Settings()
