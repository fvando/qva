"""`BrowserCamera` — a câmera é do dispositivo que abre a interface (TASK-b).

Ao contrário das outras fontes, esta não abre hardware no servidor. O browser
(tipicamente um telemóvel) captura da sua própria câmera via `getUserMedia`,
envia um JPEG para `POST /api/camera/upload-frame`, e o servidor guarda-o aqui.
`capture()` devolve o último frame recebido.

Isto permite usar a câmera do telemóvel sem instalar nada.
"""

from __future__ import annotations

import threading
import time

import cv2
import numpy as np

from app.camera.base import CameraError, CameraSource

# Um frame carregado só é válido durante este tempo (evita resolver uma questão
# antiga se o browser parou de enviar).
_FRAME_TTL_S = 15.0


class BrowserCamera(CameraSource):
    def __init__(self) -> None:
        self._frame: np.ndarray | None = None
        self._ts: float = 0.0
        self._lock = threading.Lock()

    # -- lado do servidor: recebe o frame do browser -------------------
    def set_frame_jpeg(self, jpeg: bytes) -> None:
        """Descodifica e guarda um JPEG enviado pelo browser."""
        arr = np.frombuffer(jpeg, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise CameraError("frame do browser não é um JPEG válido")
        with self._lock:
            self._frame = img
            self._ts = time.monotonic()

    # -- CameraSource ---------------------------------------------------
    def open(self) -> None:
        pass  # nada a abrir

    def capture(self) -> np.ndarray:
        """Devolve o último frame enviado E consome-o — um frame só serve uma
        captura. Assim nunca se resolve uma questão com um frame antigo se o
        upload seguinte falhar."""
        with self._lock:
            frame = self._frame
            age = time.monotonic() - self._ts
            self._frame = None  # consumido
            self._ts = 0.0
        if frame is None:
            raise CameraError(
                "nenhum frame novo do browser — reenvia a imagem da câmera do dispositivo"
            )
        if age > _FRAME_TTL_S:
            raise CameraError("o frame do browser é demasiado antigo — captura de novo")
        return frame

    def close(self) -> None:
        with self._lock:
            self._frame = None
            self._ts = 0.0

    def is_available(self) -> bool:
        with self._lock:
            return self._frame is not None and (time.monotonic() - self._ts) <= _FRAME_TTL_S
