"""Modelo da questão extraída (saída do QuestionExtractor, entrada do Solver).

Este é um contrato estável: o extractor produz `Question`, o solver consome
`Question`, e nenhum dos dois conhece os detalhes internos do outro.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    OPEN_QUESTION = "open_question"
    CODE_QUESTION = "code_question"
    MATH_QUESTION = "math_question"
    UNKNOWN = "unknown"


class Question(BaseModel):
    """Questão académica identificada a partir da imagem.

    A extração NÃO resolve a questão — apenas estrutura o conteúdo.
    """

    type: QuestionType = QuestionType.UNKNOWN
    language: str = "pt"
    question: str = ""
    options: dict[str, str] = Field(default_factory=dict)
    """Alternativas, ex: {"A": "...", "B": "..."}. Vazio se não aplicável."""
    code: str | None = None
    formulas: str | None = None
    has_image: bool = False
    confidence: float = 0.0
