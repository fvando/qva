"""`FileCamera` — placeholder da TASK-001, implementado na TASK-012.

Permite desenvolver todo o pipeline sem webcam física
(`CAMERA_TYPE=file`, `TEST_IMAGE=...`).
"""

from __future__ import annotations

from app.camera.base import CameraSource


class FileCamera(CameraSource):
    """Devolve sempre a mesma imagem de disco. Implementação real: TASK-012."""

    def __init__(self, path: str) -> None:
        self._path = path

    def open(self) -> None:  # pragma: no cover - TASK-012
        raise NotImplementedError("FileCamera será implementada na TASK-012")

    def capture(self):  # pragma: no cover - TASK-012
        raise NotImplementedError("FileCamera será implementada na TASK-012")

    def close(self) -> None:  # pragma: no cover - TASK-012
        pass

    def is_available(self) -> bool:  # pragma: no cover - TASK-012
        return False
