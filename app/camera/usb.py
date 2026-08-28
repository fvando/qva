"""`USBCamera` — captura via OpenCV `VideoCapture` (TASK-002).

Devolve sempre um frame BGR em memória (numpy array). Nunca escreve ficheiros
(local-first). O `QuestionPipeline` só conhece a interface `CameraSource`, por
isso trocar isto por RTSP na fase 2 não lhe toca.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from app.camera.base import CameraError, CameraSource

logger = logging.getLogger(__name__)

# Nº de leituras iniciais descartadas ao abrir: as primeiras frames de uma
# webcam costumam vir escuras / com auto-exposição ainda a estabilizar.
_WARMUP_FRAMES = 3


def _parse_device(device: str) -> int | str:
    """`"0"` -> 0 (índice); um caminho como `/dev/video1` fica como está."""
    try:
        return int(device)
    except (TypeError, ValueError):
        return device


class USBCamera(CameraSource):
    def __init__(self, device: str = "0") -> None:
        self._device = _parse_device(device)
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return
        cap = cv2.VideoCapture(self._device)
        if not cap.isOpened():
            cap.release()
            raise CameraError(f"Não foi possível abrir a câmera USB {self._device!r}")
        self._cap = cap
        for _ in range(_WARMUP_FRAMES):
            cap.read()
        logger.info("USBCamera aberta", extra={"model": str(self._device)})

    def capture(self) -> np.ndarray:
        if self._cap is None or not self._cap.isOpened():
            raise CameraError("Câmera USB não está aberta; chamar open() primeiro")
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CameraError("Falha ao ler frame da câmera USB")
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_available(self) -> bool:
        """`True` se conseguimos abrir o dispositivo e ler um frame.

        Não deixa a câmera aberta se ela já não estava — é uma sonda barata para
        os health checks, não um `open()` permanente.
        """
        was_open = self._cap is not None and self._cap.isOpened()
        try:
            self.open()
            self.capture()
            return True
        except CameraError:
            return False
        finally:
            if not was_open:
                self.close()
