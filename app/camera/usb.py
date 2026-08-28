"""`USBCamera` — captura via OpenCV `VideoCapture` (TASK-002).

Devolve sempre um frame BGR em memória (numpy array). Nunca escreve ficheiros
(local-first). O `QuestionPipeline` só conhece a interface `CameraSource`, por
isso trocar isto por RTSP na fase 2 não lhe toca.

No Windows o backend por omissão (MSMF) por vezes abre o dispositivo mas falha
silenciosamente em `read()`. Tentamos DirectShow (`CAP_DSHOW`) como alternativa.
"""

from __future__ import annotations

import logging
import sys

import cv2
import numpy as np

from app.camera.base import CameraError, CameraSource

logger = logging.getLogger(__name__)

# Nº de leituras iniciais descartadas ao abrir: as primeiras frames de uma
# webcam costumam vir escuras / com auto-exposição ainda a estabilizar.
_WARMUP_FRAMES = 5
# Tentativas de leitura antes de desistir (o primeiro read pode falhar).
_READ_ATTEMPTS = 5
# Abaixo deste brilho médio o frame é considerado "preto" (câmera tapada ou
# sem sinal) e não um frame válido.
_MIN_MEAN_BRIGHTNESS = 2.0

# Backends a tentar, por ordem. No Windows, DirectShow costuma ser mais fiável
# para webcams USB do que o MSMF por omissão.
if sys.platform == "win32":
    _BACKENDS = (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)
else:
    _BACKENDS = (cv2.CAP_ANY,)


def _parse_device(device: str) -> int | str:
    """`"0"` -> 0 (índice); um caminho como `/dev/video1` fica como está."""
    try:
        return int(device)
    except (TypeError, ValueError):
        return device


def _open_any_backend(device: int | str) -> cv2.VideoCapture | None:
    """Tenta abrir o dispositivo com cada backend e devolve o primeiro que
    consiga mesmo ler um frame (não basta `isOpened()`)."""
    for backend in _BACKENDS:
        cap = cv2.VideoCapture(device, backend)
        if not cap.isOpened():
            cap.release()
            continue
        for _ in range(_READ_ATTEMPTS):
            ok, frame = cap.read()
            if ok and frame is not None:
                return cap
        cap.release()
    return None


class USBCamera(CameraSource):
    def __init__(self, device: str = "0") -> None:
        self._device = _parse_device(device)
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return
        cap = _open_any_backend(self._device)
        if cap is None:
            raise CameraError(
                f"Não foi possível abrir/ler da câmera USB {self._device!r}"
            )
        self._cap = cap
        for _ in range(_WARMUP_FRAMES):
            cap.read()
        logger.info("USBCamera aberta", extra={"model": str(self._device)})

    def capture(self) -> np.ndarray:
        if self._cap is None or not self._cap.isOpened():
            raise CameraError("Câmera USB não está aberta; chamar open() primeiro")

        frame = None
        for _ in range(_READ_ATTEMPTS):
            ok, frame = self._cap.read()
            if ok and frame is not None:
                break
        else:
            raise CameraError("Falha ao ler frame da câmera USB")

        if float(frame.mean()) < _MIN_MEAN_BRIGHTNESS:
            raise CameraError(
                "Frame preto da câmera USB (tapada, desligada ou sem sinal?)"
            )
        return frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_available(self) -> bool:
        """`True` se conseguimos abrir o dispositivo e ler um frame válido.

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
