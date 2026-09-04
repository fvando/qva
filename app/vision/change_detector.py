"""`ChangeDetector` — deteta se o frame atual mostra uma questão nova (TASK-015).

Não enviamos todos os frames para o LLM. Este detetor compara o frame atual com
o de referência usando técnicas leves e devolve um score de diferença em [0, 1]:

  - **dHash** (perceptual hash 8x8): fração de bits diferentes.
  - **Histograma**: 1 - correlação dos histogramas em escala de cinza.

O score combinado é o máximo dos dois (basta um sinal forte). Acima de
`threshold` considera-se que a cena mudou.

`register()` guarda um frame como nova referência (ex: depois de capturar uma
questão). O pipeline de captura automática (TASK-016) usa isto com uma janela de
estabilização.
"""

from __future__ import annotations

import cv2
import numpy as np

DEFAULT_THRESHOLD = 0.25


def _dhash(gray: np.ndarray, hash_size: int = 8) -> np.ndarray:
    """Difference hash: compara cada pixel com o vizinho da direita."""
    small = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    return small[:, 1:] > small[:, :-1]


def _hash_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Fração de bits diferentes entre dois hashes (0 = iguais, 1 = opostos)."""
    return float(np.count_nonzero(a != b)) / a.size


def _hist_distance(a: np.ndarray, b: np.ndarray) -> float:
    """1 - correlação dos histogramas de cinza (0 = idênticos)."""
    ha = cv2.calcHist([a], [0], None, [64], [0, 256])
    hb = cv2.calcHist([b], [0], None, [64], [0, 256])
    cv2.normalize(ha, ha)
    cv2.normalize(hb, hb)
    corr = cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL)
    return float(max(0.0, min(1.0, 1.0 - corr)))


def _to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


class ChangeDetector:
    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        self._threshold = threshold
        self._ref_gray: np.ndarray | None = None
        self._ref_hash: np.ndarray | None = None

    @property
    def has_reference(self) -> bool:
        return self._ref_gray is not None

    def register(self, frame: np.ndarray) -> None:
        """Define `frame` como a nova referência."""
        gray = _to_gray(frame)
        self._ref_gray = gray
        self._ref_hash = _dhash(gray)

    def difference(self, frame: np.ndarray) -> float:
        """Score de diferença em [0, 1] entre `frame` e a referência.

        Sem referência ainda -> 1.0 (tudo é "novo").
        """
        if self._ref_gray is None or self._ref_hash is None:
            return 1.0
        gray = _to_gray(frame)
        return max(
            _hash_distance(_dhash(gray), self._ref_hash),
            _hist_distance(gray, self._ref_gray),
        )

    def is_new_question(self, frame: np.ndarray) -> bool:
        """`True` se a cena mudou o suficiente face à referência."""
        return self.difference(frame) >= self._threshold
