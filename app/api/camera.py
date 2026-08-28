"""Endpoints da câmera: status (TASK-002), preview e stream MJPEG (TASK-003)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from app.camera.base import CameraError, CameraSource
from app.config import Settings, get_settings
from app.dependencies import get_camera
from app.vision.encoding import encode_jpeg

router = APIRouter(prefix="/api/camera", tags=["camera"])

# Fronteira do multipart/x-mixed-replace usado pelo stream MJPEG.
_BOUNDARY = "qvaframe"
# Cadência do stream: ~10 fps é suficiente para posicionar a tela e poupa CPU.
_STREAM_INTERVAL_S = 0.1


@router.get("/status")
async def camera_status(
    settings: Settings = Depends(get_settings),
    camera: CameraSource = Depends(get_camera),
) -> dict:
    available = await asyncio.to_thread(camera.is_available)
    return {
        "available": available,
        "type": settings.camera_type.value,
        "device": settings.camera_device,
    }


async def _grab_jpeg(camera: CameraSource) -> bytes:
    """Abre (se preciso), captura um frame e devolve-o como JPEG, fora do loop."""

    def _work() -> bytes:
        camera.open()
        return encode_jpeg(camera.capture())

    return await asyncio.to_thread(_work)


@router.get("/frame")
async def camera_frame(camera: CameraSource = Depends(get_camera)) -> Response:
    """Um único frame atual, como JPEG. Para preview leve / posicionamento."""
    try:
        jpeg = await _grab_jpeg(camera)
    except (CameraError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return Response(content=jpeg, media_type="image/jpeg")


def _mjpeg_part(jpeg: bytes) -> bytes:
    return (
        b"--" + _BOUNDARY.encode() + b"\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
        + jpeg + b"\r\n"
    )


async def mjpeg_frames(camera: CameraSource, max_frames: int | None = None):
    """Gerador de partes MJPEG. `max_frames=None` = infinito (uso real);
    limitado nos testes para não bloquear."""
    sent = 0
    while max_frames is None or sent < max_frames:
        try:
            jpeg = await _grab_jpeg(camera)
        except (CameraError, ValueError):
            break  # câmera indisponível a meio do stream: encerra sem rebentar
        yield _mjpeg_part(jpeg)
        sent += 1
        await asyncio.sleep(_STREAM_INTERVAL_S)


@router.get("/stream")
async def camera_stream(camera: CameraSource = Depends(get_camera)) -> StreamingResponse:
    """Stream MJPEG (`multipart/x-mixed-replace`) para preview em tempo real."""
    return StreamingResponse(
        mjpeg_frames(camera),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )
