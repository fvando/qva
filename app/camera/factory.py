"""Fábrica de `CameraSource` a partir da configuração.

Centraliza a decisão "que classe de câmera instanciar" num único ponto, para
que o resto da aplicação nunca faça `if camera_type == ...`.
"""

from __future__ import annotations

from app.camera.base import CameraSource
from app.camera.file_camera import FileCamera
from app.camera.usb import USBCamera
from app.config import CameraType, Settings


def build_camera(settings: Settings) -> CameraSource:
    if settings.camera_type is CameraType.USB:
        return USBCamera(device=settings.camera_device)
    if settings.camera_type is CameraType.FILE:
        return FileCamera(path=settings.test_image)
    # rtsp / http chegam na fase 2 (TASK-017)
    raise NotImplementedError(
        f"CAMERA_TYPE={settings.camera_type.value} ainda não suportado"
    )
