"""TASK-007 + estratégia ocr/vision/hybrid — QuestionExtractor."""

import numpy as np
import pytest

from app.config import Settings
from app.llm.json_utils import JsonExtractionError, extract_json_object
from app.models.question import QuestionType
from app.vision.extractor import QuestionExtractionError, QuestionExtractor
from app.vision.ocr import OCREngine
from app.vision.processor import ProcessedImage
from tests.conftest import FakeLLM

_OCR_QUESTION = "Qual estrutura de dados segue a politica LIFO? A) Fila B) Pilha C) Arvore D) Lista"


def _processed() -> ProcessedImage:
    return ProcessedImage(image=np.full((80, 120, 3), 230, dtype=np.uint8))


def _settings(mode: str = "ocr", vision: bool = False) -> Settings:
    return Settings(_env_file=None, llm_mode=mode, llm_supports_vision=vision)


class FakeOCR(OCREngine):
    def __init__(self, text: str = _OCR_QUESTION) -> None:
        self.text = text
        self.called = False

    def image_to_text(self, image) -> str:
        self.called = True
        return self.text


def _flat(question="Qual estrutura de dados segue a politica LIFO", answer="B"):
    return (
        f'{{"type":"multiple_choice","language":"pt","question":"{question}",'
        f'"options":{{"A":"Fila","B":"Pilha"}},"answer":"{answer}",'
        f'"answer_text":"Pilha","explanation":"LIFO=pilha","confidence":0.9}}'
    )


# -- json_utils ----------------------------------------------------------
def test_extract_json_plain():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_from_fence():
    assert extract_json_object('```json\n{"a": 2}\n```') == {"a": 2}


def test_extract_json_raises_when_absent():
    with pytest.raises(JsonExtractionError):
        extract_json_object("nenhum json aqui")


# -- modo ocr ---------------------------------------------------------
async def test_ocr_extract_and_solve():
    llm = FakeLLM(text=_flat())
    ocr = FakeOCR()
    ex = QuestionExtractor(llm=llm, settings=_settings("ocr"), ocr=ocr)

    q, r = await ex.extract_and_solve(_processed())
    assert ocr.called is True
    assert llm.calls[0].image_b64 is None
    assert q.type is QuestionType.MULTIPLE_CHOICE
    assert q.options == {"A": "Fila", "B": "Pilha"}
    assert r.answer == "B"


async def test_ocr_too_little_text_raises():
    ex = QuestionExtractor(
        llm=FakeLLM(text=_flat()), settings=_settings("ocr"), ocr=FakeOCR("ab")
    )
    with pytest.raises(QuestionExtractionError):
        await ex.extract_and_solve(_processed())


async def test_ocr_hallucination_detected():
    # o LLM devolve um enunciado sem relação com o texto do OCR
    body = _flat(question="Qual e a capital de Franca", answer="A")
    ex = QuestionExtractor(
        llm=FakeLLM(text=body), settings=_settings("ocr"), ocr=FakeOCR()
    )
    with pytest.raises(QuestionExtractionError):
        await ex.extract_and_solve(_processed())


async def test_ocr_non_json_raises():
    ex = QuestionExtractor(
        llm=FakeLLM(text="não consegui"), settings=_settings("ocr"), ocr=FakeOCR()
    )
    with pytest.raises(QuestionExtractionError):
        await ex.extract_and_solve(_processed())


# -- modo vision ----------------------------------------------------
async def test_vision_extract_and_solve_sends_image():
    vis = FakeLLM(text=_flat())
    ex = QuestionExtractor(
        llm=FakeLLM(), settings=_settings("vision", vision=True),
        ocr=FakeOCR(), vision_llm=vis,
    )
    q, r = await ex.extract_and_solve(_processed())
    assert vis.calls[0].image_b64 is not None
    assert q.type is QuestionType.MULTIPLE_CHOICE
    assert r.answer == "B"


async def test_vision_mode_without_client_falls_back_to_ocr():
    llm = FakeLLM(text=_flat())
    ex = QuestionExtractor(
        llm=llm, settings=_settings("vision"), ocr=FakeOCR(), vision_llm=None
    )
    assert ex.supports_combined is True  # caiu para ocr
    q, _ = await ex.extract_and_solve(_processed())
    assert llm.calls[0].image_b64 is None


# -- modo hybrid --------------------------------------------------
async def test_hybrid_uses_ocr_when_it_works():
    text_llm = FakeLLM(text=_flat())
    vis = FakeLLM(text=_flat())
    ex = QuestionExtractor(
        llm=text_llm, settings=_settings("hybrid", vision=False),
        ocr=FakeOCR(), vision_llm=vis,
    )
    await ex.extract_and_solve(_processed())
    assert len(text_llm.calls) == 1
    assert len(vis.calls) == 0  # não foi preciso o fallback


async def test_hybrid_falls_back_to_vision_on_hallucination():
    # OCR path devolve enunciado que não bate -> guard falha -> vision
    text_llm = FakeLLM(text=_flat(question="Qual e a capital de Franca", answer="A"))
    vis = FakeLLM(text=_flat())
    ex = QuestionExtractor(
        llm=text_llm, settings=_settings("hybrid"),
        ocr=FakeOCR(), vision_llm=vis,
    )
    q, r = await ex.extract_and_solve(_processed())
    assert len(vis.calls) == 1  # fallback aconteceu
    assert vis.calls[0].image_b64 is not None
    assert r.answer == "B"


async def test_hybrid_falls_back_on_weak_ocr():
    text_llm = FakeLLM(text=_flat())
    vis = FakeLLM(text=_flat())
    ex = QuestionExtractor(
        llm=text_llm, settings=_settings("hybrid"),
        ocr=FakeOCR("xx"), vision_llm=vis,
    )
    await ex.extract_and_solve(_processed())
    assert len(vis.calls) == 1


async def test_hybrid_without_vision_client_raises_on_failure():
    ex = QuestionExtractor(
        llm=FakeLLM(text=_flat()), settings=_settings("hybrid"),
        ocr=FakeOCR("x"), vision_llm=None,
    )
    with pytest.raises(QuestionExtractionError):
        await ex.extract_and_solve(_processed())


# -- parsing robusto -------------------------------------------------
async def test_unknown_type_falls_back():
    body = (
        '{"type":"charada","question":"Qual estrutura de dados segue a politica '
        'LIFO Fila Pilha","options":{},"answer":"x"}'
    )
    ex = QuestionExtractor(llm=FakeLLM(text=body), settings=_settings("ocr"), ocr=FakeOCR())
    q, _ = await ex.extract_and_solve(_processed())
    assert q.type is QuestionType.UNKNOWN


async def test_confidence_clamped():
    body = _flat().replace('"confidence":0.9', '"confidence":9')
    ex = QuestionExtractor(llm=FakeLLM(text=body), settings=_settings("ocr"), ocr=FakeOCR())
    q, _ = await ex.extract_and_solve(_processed())
    assert q.confidence == 1.0


def test_json_repair_truncated():
    from app.llm.json_utils import extract_json_object
    trunc = '{"answer":"B","options":{"A":"x","B":"y"},"explanation":"texto cortado a meio'
    d = extract_json_object(trunc)
    assert d["answer"] == "B"
    assert d["options"] == {"A": "x", "B": "y"}
