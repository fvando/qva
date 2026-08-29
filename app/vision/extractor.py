"""`QuestionExtractor` — extrai uma `Question` estruturada (TASK-007).

Modos, escolhidos internamente por `LLM_SUPPORTS_VISION`:
  - Modo A (multimodal): a imagem tratada vai direto ao modelo Vision. Extração
    e resolução são 2 chamadas separadas (a resolução é do `QuestionSolver`).
  - Modo B (OCR + LLM): imagem -> OCR -> texto -> modelo textual. Como o input
    já é texto, `extract_and_solve()` funde extração + resolução numa só
    chamada, poupando um round-trip ao LLM (relevante em CPU).

Quem chama (`QuestionPipeline`) não sabe qual modo está ativo.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.llm.base import LLMClient, LLMRequest
from app.llm.json_utils import JsonExtractionError, clamp01, extract_json_object
from app.llm.prompts import (
    COMBINED_SYSTEM,
    EXTRACTION_SYSTEM,
    EXTRACTION_USER,
    build_combined_user,
)
from app.models.question import Question, QuestionType
from app.models.result import SolveResult
from app.vision.encoding import encode_jpeg
from app.vision.ocr import OCREngine, build_ocr_engine
from app.vision.processor import ProcessedImage

logger = logging.getLogger(__name__)


class QuestionExtractionError(RuntimeError):
    """Falha ao interpretar a resposta do LLM como uma questão."""


class QuestionExtractor:
    def __init__(
        self,
        llm: LLMClient,
        settings: Settings,
        ocr: OCREngine | None = None,
    ) -> None:
        self._llm = llm
        self._settings = settings
        self._ocr = ocr  # construído sob procura no modo B (build_ocr_engine)

    @property
    def supports_combined(self) -> bool:
        """No modo B (texto) podemos fundir extração + resolução."""
        return not self._settings.llm_supports_vision

    def _get_ocr(self) -> OCREngine:
        if self._ocr is None:
            self._ocr = build_ocr_engine()
        return self._ocr

    # -- extração isolada (usada no modo A; modo B se combined desligado) --
    async def extract(self, processed: ProcessedImage) -> Question:
        if self._settings.llm_supports_vision:
            request = await self._build_multimodal_request(processed)
        else:
            request = await self._build_ocr_request(processed)
        response = await self._llm.generate(request)
        return self._parse_question(_json(response.text))

    # -- extração + resolução numa só chamada (modo B) -----------------
    async def extract_and_solve(
        self, processed: ProcessedImage
    ) -> tuple[Question, SolveResult]:
        ocr = self._get_ocr()
        text = await asyncio.to_thread(ocr.image_to_text, processed.image)
        logger.info("OCR_DONE", extra={"model": str(len(text))})
        request = LLMRequest(
            system=COMBINED_SYSTEM, prompt=build_combined_user(text)
        )
        response = await self._llm.generate(request)
        data = _json(response.text)
        # JSON plano: os campos da questão e do resultado no mesmo nível.
        question = self._parse_question(data)
        result = _parse_result(data, question)
        return question, result

    # -- modo A -------------------------------------------------------------
    async def _build_multimodal_request(self, processed: ProcessedImage) -> LLMRequest:
        image_b64 = await asyncio.to_thread(_encode_b64, processed.image)
        return LLMRequest(
            system=EXTRACTION_SYSTEM, prompt=EXTRACTION_USER, image_b64=image_b64
        )

    # -- modo B (extração isolada) -------------------------------------
    async def _build_ocr_request(self, processed: ProcessedImage) -> LLMRequest:
        ocr = self._get_ocr()
        text = await asyncio.to_thread(ocr.image_to_text, processed.image)
        return LLMRequest(
            system=EXTRACTION_SYSTEM,
            prompt=f"{EXTRACTION_USER}\n\nTexto reconhecido:\n{text}",
        )

    # -- parsing ----------------------------------------------------------
    @staticmethod
    def _parse_question(data: dict) -> Question:
        raw_type = str(data.get("type", "unknown")).strip().lower()
        try:
            qtype = QuestionType(raw_type)
        except ValueError:
            qtype = QuestionType.UNKNOWN

        options = data.get("options") or {}
        if not isinstance(options, dict):
            options = {}
        options = {str(k): str(v) for k, v in options.items()}

        return Question(
            type=qtype,
            language=str(data.get("language") or "pt"),
            question=str(data.get("question") or ""),
            options=options,
            code=_opt_str(data.get("code")),
            formulas=_opt_str(data.get("formulas")),
            has_image=bool(data.get("has_image", False)),
            confidence=clamp01(data.get("confidence", 0.0)),
        )


def _json(text: str) -> dict:
    try:
        return extract_json_object(text)
    except JsonExtractionError as exc:
        raise QuestionExtractionError(f"resposta não-JSON: {exc}") from exc


def _parse_result(data: dict, question: Question) -> SolveResult:
    answer = str(data.get("answer") or "").strip()
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


def _encode_b64(image) -> str:
    import base64

    return base64.b64encode(encode_jpeg(image)).decode("ascii")


def _opt_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
