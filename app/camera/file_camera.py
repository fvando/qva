"""`FileCamera` — fonte de imagem a partir de um ficheiro (TASK-012).

Permite desenvolver e testar todo o pipeline sem webcam física:

    CAMERA_TYPE=file
    TEST_IMAGE=tests/fixtures/question.jpg

Devolve sempre uma cópia da mesma imagem (carregada uma vez em `open()`), como
array BGR — igual ao que a `USBCamera` devolveria.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from app.camera.base import CameraError, CameraSource

logger = logging.getLogger(__name__)


class FileCamera(CameraSource):
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._image: np.ndarray | None = None

    def open(self) -> None:
        if self._image is not None:
            return
        if not self._path.is_file():
            raise CameraError(f"TEST_IMAGE não encontrada: {self._path}")
        # `cv2.imread` não lê caminhos non-ASCII no Windows; usa imdecode.
        data = np.fromfile(str(self._path), dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            raise CameraError(f"TEST_IMAGE não é uma imagem válida: {self._path}")
        self._image = image
        logger.info("FileCamera aberta", extra={"model": str(self._path)})

    def capture(self) -> np.ndarray:
        if self._image is None:
            raise CameraError("FileCamera não está aberta; chamar open() primeiro")
        return self._image.copy()

    def close(self) -> None:
        self._image = None

    def is_available(self) -> bool:
        return self._path.is_file()
