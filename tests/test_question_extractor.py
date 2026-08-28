"""TASK-007 — QuestionExtractor (modo A e modo B) + parsing de JSON."""

import numpy as np
import pytest

from app.config import Settings
from app.llm.json_utils import JsonExtractionError, extract_json_object
from app.models.question import QuestionType
from app.vision.extractor import QuestionExtractionError, QuestionExtractor
from app.vision.ocr import OCREngine
from app.vision.processor import ProcessedImage
from tests.conftest import FakeLLM


def _processed() -> ProcessedImage:
    return ProcessedImage(image=np.full((80, 120, 3), 230, dtype=np.uint8))


def _settings(vision: bool) -> Settings:
    return Settings(_env_file=None, llm_supports_vision=vision)


class FakeOCR(OCREngine):
    def __init__(self, text: str) -> None:
        self.text = text
        self.called = False

    def image_to_text(self, image) -> str:
        self.called = True
        return self.text


# -- json_utils ----------------------------------------------------------
def test_extract_json_plain():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_from_fence():
    assert extract_json_object('```json\n{"a": 2}\n```') == {"a": 2}


def test_extract_json_with_surrounding_text():
    txt = 'Claro! Aqui está:\n{"answer": "D"}\nEspero ter ajudado.'
    assert extract_json_object(txt) == {"answer": "D"}


def test_extract_json_raises_when_absent():
    with pytest.raises(JsonExtractionError):
        extract_json_object("nenhum json aqui")


# -- modo A (multimodal) --------------------------------------------------
async def test_mode_a_sends_image_and_parses():
    body = (
        '{"type":"multiple_choice","language":"pt","question":"Qual?",'
        '"options":{"A":"um","B":"dois"},"code":null,"has_image":false,'
        '"confidence":0.9}'
    )
    llm = FakeLLM(text=body)
    ex = QuestionExtractor(llm=llm, settings=_settings(vision=True), ocr=FakeOCR("x"))
    q = await ex.extract(_processed())

    assert q.type is QuestionType.MULTIPLE_CHOICE
    assert q.options == {"A": "um", "B": "dois"}
    assert q.confidence == 0.9
    assert llm.calls[0].image_b64 is not None  # imagem foi enviada


# -- modo B (OCR + LLM) --------------------------------------------------
async def test_mode_b_uses_ocr_and_no_image():
    llm = FakeLLM(text='{"type":"open_question","question":"Explique X"}')
    ocr = FakeOCR("Explique X detalhadamente")
    ex = QuestionExtractor(llm=llm, settings=_settings(vision=False), ocr=ocr)
    q = await ex.extract(_processed())

    assert ocr.called is True
    assert llm.calls[0].image_b64 is None
    assert "Explique X detalhadamente" in llm.calls[0].prompt
    assert q.type is QuestionType.OPEN_QUESTION


# -- robustez do parsing ----------------------------------------------
async def test_unknown_type_falls_back():
    llm = FakeLLM(text='{"type":"charada","question":"?"}')
    ex = QuestionExtractor(llm=llm, settings=_settings(vision=True))
    q = await ex.extract(_processed())
    assert q.type is QuestionType.UNKNOWN


async def test_confidence_is_clamped():
    llm = FakeLLM(text='{"type":"true_false","question":"?","confidence":5}')
    ex = QuestionExtractor(llm=llm, settings=_settings(vision=True))
    q = await ex.extract(_processed())
    assert q.confidence == 1.0


async def test_non_json_response_raises():
    llm = FakeLLM(text="Desculpe, não consegui.")
    ex = QuestionExtractor(llm=llm, settings=_settings(vision=True))
    with pytest.raises(QuestionExtractionError):
        await ex.extract(_processed())


async def test_options_non_dict_becomes_empty():
    llm = FakeLLM(text='{"type":"multiple_choice","question":"?","options":["a","b"]}')
    ex = QuestionExtractor(llm=llm, settings=_settings(vision=True))
    q = await ex.extract(_processed())
    assert q.options == {}
