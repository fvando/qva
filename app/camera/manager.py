"""`CameraManager` — câmera ativa mutável em runtime (escolha na UI).

O `.env` define a câmera inicial. A partir daí, a UI pode trocar de câmera
(`POST /api/camera/select`) sem reiniciar o servidor. O `CameraManager`
mantém uma só `CameraSource` ativa, fecha a anterior ao trocar, e é o que o
resto da app recebe via `Depends`.
"""

from __future__ import annotations

import logging
import threading
import time

from app.camera.base import CameraError, CameraSource
from app.camera.browser import BrowserCamera
from app.camera.factory import build_camera
from app.camera.file_camera import FileCamera
from app.camera.rtsp import HTTPIPCamera, RTSPCamera
from app.camera.usb import USBCamera, list_video_input_names, probe_device
from app.config import CameraType, Settings

logger = logging.getLogger(__name__)

# Índices USB a sondar ao listar dispositivos.
_MAX_USB_PROBE = 5
# Quanto tempo o resultado de is_available() é reaproveitado sem voltar a sondar
# a câmera. Evita que /health (15s) + /api/camera/status abram/fechem a webcam
# repetidamente — a webcam USB é lenta a re-inicializar e isso causava falhas.
_AVAILABILITY_CACHE_S = 8.0


class CameraManager(CameraSource):
    """`CameraSource` que delega numa câmera ativa trocável.

    Todo o acesso à câmera é serializado por um lock reentrante — vários
    pedidos HTTP concorrentes (preview, status, captura) partilham a mesma
    `VideoCapture`, que não é thread-safe.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.RLock()
        # A câmera do browser tem estado (o último frame enviado) — instância
        # única, reutilizada sempre que se voltar a `browser`.
        self._browser = BrowserCamera()
        if settings.camera_type is CameraType.BROWSER:
            self._active: CameraSource = self._browser
        else:
            self._active = build_camera(settings)
        self._desc = _describe(settings.camera_type.value, _initial_target(settings))
        self._avail_value = False
        self._avail_ts = 0.0

    @property
    def browser_camera(self) -> BrowserCamera:
        return self._browser

    # -- CameraSource: delega tudo na ativa, serializado --------------
    def open(self) -> None:
        with self._lock:
            self._active.open()

    def capture(self):
        with self._lock:
            self._active.open()  # garante aberta (idempotente)
            frame = self._active.capture()
        self._mark_available(True)
        return frame

    def close(self) -> None:
        with self._lock:
            self._active.close()

    def is_available(self) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._avail_ts < _AVAILABILITY_CACHE_S:
                return self._avail_value
            try:
                self._active.open()
                self._active.capture()
                ok = True
            except CameraError:
                ok = False
            self._avail_value = ok
            self._avail_ts = now
        return ok

    def _mark_available(self, ok: bool) -> None:
        with self._lock:
            self._avail_value = ok
            self._avail_ts = time.monotonic()

    # -- gestão da câmera ativa --------------------------------------
    @property
    def description(self) -> dict:
        return dict(self._desc)

    def select(self, kind: str, target: str) -> dict:
        """Troca a câmera ativa. `kind`: usb|file|rtsp|http|browser.
        `target`: índice do dispositivo (usb), caminho (file) ou URL (rtsp/http);
        ignorado para `browser`."""
        kind = kind.lower().strip()

        if kind == "browser":
            with self._lock:
                old = self._active
                self._active = self._browser
                self._desc = _describe("browser", "")
            if old is not self._browser:
                _safe_close(old)
            logger.info("CAMERA_SELECTED", extra={"model": "browser"})
            return self.description

        new = _build(kind, target, self._settings)

        # Valida antes de assumir — não queremos ficar sem câmera se falhar.
        if not new.is_available():
            new.close()
            raise CameraError(f"câmera {kind}:{target} não está disponível")

        with self._lock:
            old = self._active
            self._active = new
            self._desc = _describe(kind, target)
        if old is not self._browser:
            _safe_close(old)
        logger.info("CAMERA_SELECTED", extra={"model": f"{kind}:{target}"})
        return self.description

    def list_devices(self) -> list[dict]:
        """Lista as câmeras de vídeo disponíveis.

        No Windows usa a enumeração DirectShow (`pygrabber`) — instantânea e
        com os nomes reais. Sem ela, cai numa sonda por índice.

        Nunca levanta exceção — devolve `[]` no pior caso.
        """
        try:
            names = list_video_input_names()
        except Exception:  # noqa: BLE001
            names = None
        if names is not None:
            return [
                {"kind": "usb", "target": str(i), "label": f"{name} (índice {i})"}
                for i, name in enumerate(names)
            ]

        # Fallback: sondar índices (em série; abrir VideoCapture em paralelo
        # noutras threads é instável no Windows).
        found: list[dict] = []
        for idx in range(_MAX_USB_PROBE):
            try:
                if probe_device(idx) is not None:
                    found.append(
                        {"kind": "usb", "target": str(idx), "label": f"Câmera {idx}"}
                    )
            except Exception:  # noqa: BLE001
                break
        return found


def _safe_close(cam: CameraSource) -> None:
    try:
        cam.close()
    except Exception:  # noqa: BLE001
        pass


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
