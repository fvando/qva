"""Modelos de resultado: resposta do solver, métricas e resposta consolidada."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.question import Question


class SolveResult(BaseModel):
    """Resposta do QuestionSolver (já validada e normalizada)."""

    answer: str = ""
    answer_text: str = ""
    explanation: str = ""
    confidence: float = 0.0
    ambiguous: bool = False


class Timing(BaseModel):
    """Latência instrumentada de cada passo do pipeline, em milissegundos."""

    capture_ms: float = 0.0
    image_processing_ms: float = 0.0
    question_extraction_ms: float = 0.0
    llm_ms: float = 0.0
    total_ms: float = 0.0


class CaptureResponse(BaseModel):
    """Resposta imediata de `POST /api/capture` (processamento assíncrono)."""

    capture_id: str
    status: str = "processing"


class ConsolidatedResponse(BaseModel):
    """Resposta final consolidada, entregue via API e via WebSocket."""

    id: str
    status: str = "completed"
    question: Question | None = None
    result: SolveResult | None = None
    timing: Timing = Field(default_factory=Timing)
    error: str | None = None
