"""`QuestionSolver` — resolve uma `Question` já estruturada (TASK-008).

Separado por completo da extração: recebe a `Question`, monta o prompt de
resolução (secção 12), chama o `LLMClient`, valida/normaliza o JSON de retorno,
trata erros e mede latência.
"""

from __future__ import annotations

import logging
import time

from app.llm.base import LLMClient, LLMError, LLMRequest
from app.llm.json_utils import JsonExtractionError, clamp01, extract_json_object
from app.llm.prompts import SOLVE_SYSTEM, build_solve_user
from app.models.question import Question
from app.models.result import SolveResult

logger = logging.getLogger(__name__)


class QuestionSolveError(RuntimeError):
    """Falha ao resolver a questão (LLM indisponível ou resposta inválida)."""


class QuestionSolver:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def solve(self, question: Question) -> SolveResult:
        request = LLMRequest(
            system=SOLVE_SYSTEM,
            prompt=build_solve_user(question.model_dump_json()),
        )

        t0 = time.perf_counter()
        try:
            response = await self._llm.generate(request)
        except LLMError as exc:
            raise QuestionSolveError(f"LLM falhou ({exc.kind})") from exc
        latency_ms = (time.perf_counter() - t0) * 1000

        result = self._parse(response.text, question)
        logger.info(
            "ANSWER_READY",
            extra={"model": response.model, "latency_ms": round(latency_ms, 1)},
        )
        return result

    @staticmethod
    def _parse(text: str, question: Question) -> SolveResult:
        try:
            data = extract_json_object(text)
        except JsonExtractionError as exc:
            raise QuestionSolveError(f"resposta não-JSON: {exc}") from exc

        answer = str(data.get("answer") or "").strip()

        # Se o LLM devolveu só a letra, completa o texto a partir das opções.
        answer_text = str(data.get("answer_text") or "").strip()
        if not answer_text and answer in question.options:
            answer_text = question.options[answer]

        return SolveResult(
            answer=answer,
            answer_text=answer_text,
            explanation=str(data.get("explanation") or "").strip(),
            confidence=clamp01(data.get("confidence", 0.0)),
            ambiguous=bool(data.get("ambiguous", False)),
        )
