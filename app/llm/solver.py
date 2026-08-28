"""`QuestionSolver` — placeholder da TASK-001, implementado na TASK-008.

Separado por completo da extração: recebe uma `Question` já estruturada,
monta o prompt de resolução, chama o `LLMClient`, valida e normaliza o JSON
da resposta, trata erros e mede latência.
"""

from __future__ import annotations

from app.llm.base import LLMClient
from app.models.question import Question
from app.models.result import SolveResult


class QuestionSolver:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def solve(
        self, question: Question
    ) -> SolveResult:  # pragma: no cover - TASK-008
        raise NotImplementedError("QuestionSolver será implementado na TASK-008")
