"""Modelos de dados partilhados (contratos entre módulos)."""

from app.models.question import Question, QuestionType
from app.models.result import (
    CaptureResponse,
    ConsolidatedResponse,
    SolveResult,
    Timing,
)

__all__ = [
    "Question",
    "QuestionType",
    "SolveResult",
    "Timing",
    "CaptureResponse",
    "ConsolidatedResponse",
]
