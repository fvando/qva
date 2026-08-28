"""Encoding de frames para JPEG em memória (local-first).

Nunca usa `cv2.imwrite` — o frame vai de numpy array para bytes JPEG
diretamente na RAM, conforme a secção 20 do prompt.
"""

from __future__ import annotations

import cv2
import numpy as np


def encode_jpeg(frame: np.ndarray, quality: int = 85) -> bytes:
    """Codifica um frame BGR como JPEG. Levanta `ValueError` se falhar."""
    if frame is None or frame.size == 0:
        raise ValueError("Frame vazio; nada para codificar")
    try:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    except cv2.error as exc:  # noqa: BLE001 - normaliza para ValueError
        raise ValueError(f"Falha ao codificar frame como JPEG: {exc}") from exc
    if not ok:
        raise ValueError("Falha ao codificar frame como JPEG")
    return bytes(buf)
