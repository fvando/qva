"""`QuestionExtractor` — placeholder da TASK-001, implementado na TASK-007.

Suporta dois modos, escolhidos internamente a partir de `LLM_SUPPORTS_VISION`:
  - Modo A (multimodal): envia a imagem diretamente ao modelo Vision.
  - Modo B (OCR + LLM): imagem -> OCR -> texto -> LLM.
O código de negócio não deve depender de qual modo está ativo.
"""

from __future__ import annotations

from app.models.question import Question
from app.vision.processor import ProcessedImage


class QuestionExtractor:
    """Extrai uma `Question` estruturada de uma imagem tratada.

    Implementação real: TASK-007.
    """

    async def extract(
        self, processed: ProcessedImage
    ) -> Question:  # pragma: no cover - TASK-007
        raise NotImplementedError("QuestionExtractor será implementado na TASK-007")
