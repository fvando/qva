"""`ImageProcessor` — placeholder da TASK-001, implementado na TASK-005."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProcessedImage:
    """Imagem tratada + métricas de qualidade."""

    image: object  # np.ndarray — evita importar numpy no import da app
    sharpness_score: float = 0.0
    brightness_score: float = 0.0
    perspective_score: float = 0.0


class ImageQualityError(RuntimeError):
    """Imagem imprópria para interpretação (blur, brilho, perspetiva)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ImageProcessor:
    """Recorte, correção de perspetiva, deskew, contraste, métricas.

    Implementação real: TASK-005.
    """

    async def process(self, frame) -> ProcessedImage:  # pragma: no cover - TASK-005
        raise NotImplementedError("ImageProcessor será implementado na TASK-005")
