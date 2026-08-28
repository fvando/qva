"""`ChangeDetector` — placeholder da TASK-001, implementado na TASK-015."""

from __future__ import annotations


class ChangeDetector:
    """Deteta se o frame atual difere significativamente do anterior
    (perceptual hash / SSIM / histograma). Implementação real: TASK-015.
    """

    def __init__(self, threshold: float = 0.25) -> None:
        self._threshold = threshold

    def is_new_question(self, frame) -> bool:  # pragma: no cover - TASK-015
        raise NotImplementedError("ChangeDetector será implementado na TASK-015")
