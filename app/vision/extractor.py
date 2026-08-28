"""`QuestionExtractor` — extrai uma `Question` estruturada (TASK-007).

Dois modos, escolhidos internamente por `LLM_SUPPORTS_VISION`:
  - Modo A (multimodal): a imagem tratada vai direto ao modelo Vision.
  - Modo B (OCR + LLM): imagem -> OCR -> texto -> modelo textual.

Quem chama (`QuestionPipeline`) não sabe qual modo está ativo — só recebe uma
`Question`.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.llm.base import LLMClient, LLMRequest
from app.llm.json_utils import JsonExtractionError, extract_json_object
from app.llm.prompts import EXTRACTION_SYSTEM, EXTRACTION_USER
from app.models.question import Question, QuestionType
from app.vision.encoding import encode_jpeg
from app.vision.ocr import OCREngine, TesseractOCR
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
        self._ocr = ocr or TesseractOCR()

    async def extract(self, processed: ProcessedImage) -> Question:
        if self._settings.llm_supports_vision:
            request = await self._build_multimodal_request(processed)
        else:
            request = await self._build_ocr_request(processed)

        response = await self._llm.generate(request)
        return self._parse(response.text)

    # -- modo A -------------------------------------------------------------
    async def _build_multimodal_request(self, processed: ProcessedImage) -> LLMRequest:
        image_b64 = await asyncio.to_thread(_encode_b64, processed.image)
        return LLMRequest(
            system=EXTRACTION_SYSTEM,
            prompt=EXTRACTION_USER,
            image_b64=image_b64,
        )

    # -- modo B -------------------------------------------------------------
    async def _build_ocr_request(self, processed: ProcessedImage) -> LLMRequest:
        text = await asyncio.to_thread(self._ocr.image_to_text, processed.image)
        return LLMRequest(
            system=EXTRACTION_SYSTEM,
            prompt=f"{EXTRACTION_USER}\n\nTexto reconhecido:\n{text}",
        )

    # -- parsing ----------------------------------------------------------
    @staticmethod
    def _parse(text: str) -> Question:
        try:
            data = extract_json_object(text)
        except JsonExtractionError as exc:
            raise QuestionExtractionError(f"resposta não-JSON: {exc}") from exc

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
            confidence=_clamp01(data.get("confidence", 0.0)),
        )


def _encode_b64(image) -> str:
    import base64

    return base64.b64encode(encode_jpeg(image)).decode("ascii")


def _opt_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clamp01(value) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))
