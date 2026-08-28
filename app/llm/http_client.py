"""`HttpLLMClient` — placeholder da TASK-001, implementado na TASK-006."""

from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMClient, LLMRequest, LLMResponse


class HttpLLMClient(LLMClient):
    """Fala com o serviço LLM local via HTTP (`httpx.AsyncClient`).

    Trata explicitamente timeout, ligação recusada, 4xx, 5xx, resposta
    inválida e JSON malformado. Implementação real: TASK-006.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate(
        self, request: LLMRequest
    ) -> LLMResponse:  # pragma: no cover - TASK-006
        raise NotImplementedError("HttpLLMClient será implementado na TASK-006")
