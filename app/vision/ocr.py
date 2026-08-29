"""OCR para o modo B do QuestionExtractor (imagem -> texto -> LLM).

O prompt não impõe biblioteca. Definimos a interface `OCREngine` e duas
implementações:

  - `RapidOCREngine` (`rapidocr-onnxruntime`): deep-learning via ONNX Runtime,
    **sem binário externo** — funciona com um simples `pip install`. Preferido.
  - `TesseractOCR` (`pytesseract` + binário `tesseract`): alternativa clássica.

`build_ocr_engine()` escolhe o primeiro disponível. No modo A (multimodal) este
módulo nunca é tocado.
"""

from __future__ import annotations

import abc
import logging

import numpy as np

logger = logging.getLogger(__name__)


class OCRUnavailableError(RuntimeError):
    """OCR necessário (modo B) mas nenhum motor disponível."""


class OCREngine(abc.ABC):
    @abc.abstractmethod
    def image_to_text(self, image: np.ndarray) -> str:
        ...


class RapidOCREngine(OCREngine):
    """OCR via `rapidocr-onnxruntime` (ONNX, CPU, sem binário externo)."""

    def __init__(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise OCRUnavailableError("modo B: 'rapidocr-onnxruntime' não instalado") from exc
        # Carregar os modelos ONNX uma vez (custa ~1s; reutilizado nas chamadas).
        self._engine = RapidOCR()

    def image_to_text(self, image: np.ndarray) -> str:
        result, _ = self._engine(image)
        if not result:
            return ""
        # `result` = [(box, texto, confiança), ...] em ordem de leitura.
        return "\n".join(line[1] for line in result)


class TesseractOCR(OCREngine):
    """OCR via `pytesseract` (requer o binário `tesseract` no sistema)."""

    def __init__(self, lang: str = "por+eng") -> None:
        self._lang = lang

    def image_to_text(self, image: np.ndarray) -> str:
        try:
            import pytesseract
        except ImportError as exc:  # pragma: no cover
            raise OCRUnavailableError(
                "modo B: 'pytesseract' e o binário tesseract não estão instalados"
            ) from exc
        return pytesseract.image_to_string(image, lang=self._lang)


def build_ocr_engine() -> OCREngine:
    """Devolve o primeiro motor de OCR disponível, ou levanta
    `OCRUnavailableError` se nenhum estiver instalado."""
    for factory in (RapidOCREngine, TesseractOCR):
        try:
            engine = factory()
            logger.info("OCR_ENGINE_SELECTED", extra={"model": factory.__name__})
            return engine
        except OCRUnavailableError:
            continue
    raise OCRUnavailableError(
        "modo B requer 'rapidocr-onnxruntime' ou 'pytesseract'+tesseract"
    )
