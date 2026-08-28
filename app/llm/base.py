"""Interface genérica de LLM (TASK-001; `HttpLLMClient` em TASK-006).

Não assume Ollama nem qualquer fornecedor específico. O contrato é apenas
"recebe um pedido, devolve texto" — a forma HTTP concreta é detalhe do
`HttpLLMClient`.
"""

from __future__ import annotations

import abc

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    """Pedido ao LLM, agnóstico de transporte."""

    system: str = ""
    prompt: str = ""
    image_b64: str | None = None
    """JPEG em base64, apenas quando o modelo suporta visão."""
    temperature: float = 0.0
    max_tokens: int = 1024


class LLMResponse(BaseModel):
    """Resposta bruta do LLM."""

    text: str = ""
    model: str = ""
    latency_ms: float = 0.0
    raw: dict = Field(default_factory=dict)


class LLMError(RuntimeError):
    """Falha de comunicação ou resposta inválida do serviço LLM.

    `kind` categoriza para tratamento/observabilidade:
    timeout | connection | http_4xx | http_5xx | invalid_response | bad_json
    """

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(f"[{kind}] {message}")
        self.kind = kind


class LLMClient(abc.ABC):
    """Cliente abstrato de LLM."""

    @abc.abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Executa o pedido. Levanta `LLMError` em qualquer falha."""

    async def health(self) -> bool:
        """`True` se o serviço LLM responde. Override opcional."""
        return False
