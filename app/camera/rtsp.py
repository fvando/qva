"""`RTSPCamera` / `HTTPIPCamera` — câmera IP (TASK-017, fase 2).

Mesma interface `CameraSource` que a `USBCamera`. O `QuestionPipeline`, a
captura automática e a UI não mudam nada — só a configuração:

    CAMERA_TYPE=rtsp
    CAMERA_URL=rtsp://user:pass@192.168.1.50:554/stream

Diferenças práticas face à USB, tratadas aqui:
  - o stream tem buffer: lemos e descartamos frames para apanhar o mais recente;
  - a ligação pode cair a meio -> `capture()` levanta `CameraError`, e o
    pipeline trata-o como qualquer outra falha de câmera.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from app.camera.base import CameraError, CameraSource

logger = logging.getLogger(__name__)

# Frames a descartar por captura para reduzir a latência do buffer do stream.
_FLUSH_FRAMES = 4
# Tentativas de leitura antes de desistir de um frame.
_READ_ATTEMPTS = 3


class RTSPCamera(CameraSource):
    def __init__(self, url: str) -> None:
        if not url:
            raise CameraError("CAMERA_URL vazio para CAMERA_TYPE=rtsp")
        self._url = url
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return
        # FFMPEG é o backend com melhor suporte RTSP no OpenCV.
        cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            raise CameraError(f"Não foi possível abrir o stream: {_redact(self._url)}")
        # Buffer pequeno = frame mais fresco (nem todos os backends respeitam).
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap
        logger.info("RTSPCamera aberta", extra={"model": _redact(self._url)})

    def capture(self) -> np.ndarray:
        if self._cap is None or not self._cap.isOpened():
            raise CameraError("Stream RTSP não está aberto; chamar open() primeiro")

        for _ in range(_FLUSH_FRAMES):
            self._cap.grab()

        for _ in range(_READ_ATTEMPTS):
            ok, frame = self._cap.read()
            if ok and frame is not None:
                return frame
        raise CameraError("Falha ao ler frame do stream RTSP (ligação perdida?)")

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_available(self) -> bool:
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


# `HTTPIPCamera` (MJPEG/HTTP) partilha toda a lógica — só muda o esquema do URL,
# que o OpenCV resolve de igual forma.
class HTTPIPCamera(RTSPCamera):
    """Câmera IP via HTTP/MJPEG (`CAMERA_TYPE=http`, `CAMERA_URL=http://...`)."""


def _redact(url: str) -> str:
    """Esconde credenciais embutidas no URL antes de as pôr num log."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url
