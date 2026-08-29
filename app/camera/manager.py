"""`CameraManager` — câmera ativa mutável em runtime (escolha na UI).

O `.env` define a câmera inicial. A partir daí, a UI pode trocar de câmera
(`POST /api/camera/select`) sem reiniciar o servidor. O `CameraManager`
mantém uma só `CameraSource` ativa, fecha a anterior ao trocar, e é o que o
resto da app recebe via `Depends`.
"""

from __future__ import annotations

import logging
import threading

from app.camera.base import CameraError, CameraSource
from app.camera.factory import build_camera
from app.camera.file_camera import FileCamera
from app.camera.rtsp import HTTPIPCamera, RTSPCamera
from app.camera.usb import USBCamera, list_video_input_names, probe_device
from app.config import CameraType, Settings

logger = logging.getLogger(__name__)

# Índices USB a sondar ao listar dispositivos.
_MAX_USB_PROBE = 5


class CameraManager(CameraSource):
    """`CameraSource` que delega numa câmera ativa trocável."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._active: CameraSource = build_camera(settings)
        self._lock = threading.Lock()
        self._desc = _describe(settings.camera_type.value, _initial_target(settings))

    # -- CameraSource: delega tudo na ativa ----------------------------
    def open(self) -> None:
        self._active.open()

    def capture(self):
        return self._active.capture()

    def close(self) -> None:
        self._active.close()

    def is_available(self) -> bool:
        return self._active.is_available()

    # -- gestão da câmera ativa --------------------------------------
    @property
    def description(self) -> dict:
        return dict(self._desc)

    def select(self, kind: str, target: str) -> dict:
        """Troca a câmera ativa. `kind`: usb|file|rtsp|http. `target`: índice do
        dispositivo (usb), caminho (file) ou URL (rtsp/http)."""
        kind = kind.lower().strip()
        new = _build(kind, target, self._settings)

        # Valida antes de assumir — não queremos ficar sem câmera se falhar.
        if not new.is_available():
            new.close()
            raise CameraError(f"câmera {kind}:{target} não está disponível")

        with self._lock:
            old = self._active
            self._active = new
            self._desc = _describe(kind, target)
        try:
            old.close()
        except Exception:  # noqa: BLE001
            pass
        logger.info("CAMERA_SELECTED", extra={"model": f"{kind}:{target}"})
        return self.description

    def list_devices(self) -> list[dict]:
        """Lista as câmeras de vídeo disponíveis.

        No Windows usa a enumeração DirectShow (`pygrabber`) — instantânea e
        com os nomes reais. Sem ela, cai numa sonda por índice (mais lenta).
        """
        names = list_video_input_names()
        if names is not None:
            return [
                {"kind": "usb", "target": str(i), "label": f"{name} (índice {i})"}
                for i, name in enumerate(names)
            ]
        # Fallback: sondar índices em paralelo.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=_MAX_USB_PROBE) as pool:
            backends = list(pool.map(probe_device, range(_MAX_USB_PROBE)))
        return [
            {"kind": "usb", "target": str(i), "label": f"Câmera {i} (índice {i})"}
            for i, be in enumerate(backends)
            if be is not None
        ]


def _initial_target(settings: Settings) -> str:
    if settings.camera_type is CameraType.FILE:
        return settings.test_image
    if settings.camera_type in (CameraType.RTSP, CameraType.HTTP):
        return settings.camera_url
    return settings.camera_device


def _describe(kind: str, target: str) -> dict:
    return {"type": kind, "target": target}


def _build(kind: str, target: str, settings: Settings) -> CameraSource:
    if kind == "usb":
        return USBCamera(device=target or "0")
    if kind == "file":
        return FileCamera(path=target or settings.test_image)
    if kind == "rtsp":
        return RTSPCamera(url=target)
    if kind == "http":
        return HTTPIPCamera(url=target)
    raise CameraError(f"tipo de câmera desconhecido: {kind}")
