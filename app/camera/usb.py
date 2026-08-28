"""`USBCamera` — placeholder da TASK-001, implementado na TASK-002."""

from __future__ import annotations

from app.camera.base import CameraError, CameraSource


class USBCamera(CameraSource):
    """Webcam USB via OpenCV `VideoCapture`. Implementação real: TASK-002."""

    def __init__(self, device: str = "0") -> None:
        self._device = device

    def open(self) -> None:  # pragma: no cover - TASK-002
        raise NotImplementedError("USBCamera será implementada na TASK-002")

    def capture(self):  # pragma: no cover - TASK-002
        raise NotImplementedError("USBCamera será implementada na TASK-002")

    def close(self) -> None:  # pragma: no cover - TASK-002
        pass

    def is_available(self) -> bool:  # pragma: no cover - TASK-002
        return False
