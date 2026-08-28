"""OCR opcional para o modo B do QuestionExtractor (imagem -> texto -> LLM).

O prompt não impõe uma biblioteca. Definimos uma interface `OCREngine` e uma
implementação `TesseractOCR` que usa `pytesseract` **se estiver instalado**;
caso contrário levanta um erro explícito em vez de falhar em silêncio.

No modo A (multimodal) este módulo nunca é tocado.
"""

from __future__ import annotations

import abc

import numpy as np


class OCRUnavailableError(RuntimeError):
    """OCR necessário (modo B) mas nenhum motor disponível."""


class OCREngine(abc.ABC):
    @abc.abstractmethod
    def image_to_text(self, image: np.ndarray) -> str:
        ...


class TesseractOCR(OCREngine):
    def __init__(self, lang: str = "por+eng") -> None:
        self._lang = lang

    def image_to_text(self, image: np.ndarray) -> str:
        try:
            import pytesseract  # import tardio: dependência opcional
        except ImportError as exc:  # pragma: no cover - ambiente sem pytesseract
            raise OCRUnavailableError(
                "modo B requer 'pytesseract' e o binário tesseract instalados"
            ) from exc
        return pytesseract.image_to_string(image, lang=self._lang)
