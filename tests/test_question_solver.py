"""TASK-008 — QuestionSolver."""

import pytest

from app.llm.base import LLMError
from app.llm.solver import QuestionSolveError, QuestionSolver
from app.models.question import Question, QuestionType
from tests.conftest import FakeLLM


def _mc_question() -> Question:
    return Question(
        type=QuestionType.MULTIPLE_CHOICE,
        question="Qual estrutura é LIFO?",
        options={"A": "Fila", "B": "Pilha", "C": "Árvore", "D": "Grafo"},
    )


async def test_solve_happy_path():
    body = (
        '{"answer":"B","answer_text":"Pilha","explanation":"LIFO = pilha.",'
        '"confidence":0.97,"ambiguous":false}'
    )
    result = await QuestionSolver(FakeLLM(text=body)).solve(_mc_question())
    assert result.answer == "B"
    assert result.answer_text == "Pilha"
    assert result.confidence == 0.97
    assert result.ambiguous is False


async def test_answer_text_filled_from_options_when_missing():
    body = '{"answer":"B","explanation":"...","confidence":0.8}'
    result = await QuestionSolver(FakeLLM(text=body)).solve(_mc_question())
    assert result.answer_text == "Pilha"  # veio de options["B"]


async def test_prompt_contains_question_json():
    llm = FakeLLM(text='{"answer":"A"}')
    await QuestionSolver(llm).solve(_mc_question())
    sent = llm.calls[0].prompt
    assert "LIFO" in sent
    assert "Pilha" in sent


async def test_confidence_clamped():
    body = '{"answer":"B","confidence":42}'
    result = await QuestionSolver(FakeLLM(text=body)).solve(_mc_question())
    assert result.confidence == 1.0


async def test_non_json_response_raises():
    with pytest.raises(QuestionSolveError):
        await QuestionSolver(FakeLLM(text="Não sei responder")).solve(_mc_question())


async def test_llm_error_becomes_solve_error():
    class BoomLLM(FakeLLM):
        async def generate(self, request):
            raise LLMError("http_5xx", "servidor caiu")

    with pytest.raises(QuestionSolveError):
        await QuestionSolver(BoomLLM()).solve(_mc_question())
