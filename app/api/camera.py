"""Endpoints da câmera: status (TASK-002), preview e stream MJPEG (TASK-003)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.camera.base import CameraError, CameraSource
from app.camera.manager import CameraManager
from app.dependencies import get_camera, get_camera_manager
from app.vision.encoding import encode_jpeg

router = APIRouter(prefix="/api/camera", tags=["camera"])

# Fronteira do multipart/x-mixed-replace usado pelo stream MJPEG.
_BOUNDARY = "qvaframe"
# Cadência do stream: ~10 fps é suficiente para posicionar a tela e poupa CPU.
_STREAM_INTERVAL_S = 0.1


@router.get("/status")
async def camera_status(
    manager: CameraManager = Depends(get_camera_manager),
) -> dict:
    available = await asyncio.to_thread(manager.is_available)
    desc = manager.description
    return {"available": available, "type": desc["type"], "device": desc["target"]}


@router.get("/devices")
async def camera_devices(
    manager: CameraManager = Depends(get_camera_manager),
) -> dict:
    """Lista as câmeras disponíveis no servidor e a que está ativa.

    A opção "câmera deste dispositivo" (browser) é sempre possível e não
    aparece aqui — a UI adiciona-a.
    """
    devices = await asyncio.to_thread(manager.list_devices)
    return {"active": manager.description, "devices": devices}


class SelectCameraBody(BaseModel):
    kind: str  # usb | file | rtsp | http
    target: str = ""  # índice USB, caminho de ficheiro, ou URL


@router.post("/select")
async def camera_select(
    body: SelectCameraBody,
    manager: CameraManager = Depends(get_camera_manager),
) -> dict:
    try:
        desc = await asyncio.to_thread(manager.select, body.kind, body.target)
    except CameraError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return {"active": desc}


@router.post("/upload-frame")
async def upload_frame(
    request: Request,
    manager: CameraManager = Depends(get_camera_manager),
) -> dict:
    """Recebe um JPEG capturado pela câmera do browser (`CAMERA_TYPE=browser`).

    O corpo é o JPEG binário (Content-Type image/jpeg). O frame fica disponível
    para o próximo `POST /api/capture`.
    """
    data = await request.body()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="corpo vazio"
        )
    try:
        await asyncio.to_thread(manager.browser_camera.set_frame_jpeg, data)
    except CameraError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return {"bytes": len(data)}


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
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


def _mjpeg_part(jpeg: bytes) -> bytes:
    return (
        b"--" + _BOUNDARY.encode() + b"\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
        + jpeg + b"\r\n"
    )


async def mjpeg_frames(camera: CameraSource, max_frames: int | None = None):
    """Gerador de partes MJPEG. `max_frames=None` = infinito (uso real);
    limitado nos testes para não bloquear. Nunca propaga uma exceção — um
    erro de câmera encerra o stream, não derruba o servidor."""
    sent = 0
    consecutive_errors = 0
    while max_frames is None or sent < max_frames:
        try:
            jpeg = await _grab_jpeg(camera)
            consecutive_errors = 0
        except asyncio.CancelledError:
            raise  # cliente desligou — deixa o framework tratar
        except Exception:  # noqa: BLE001
            consecutive_errors += 1
            if consecutive_errors >= 5:
                break  # câmera em baixo — encerra o stream
            await asyncio.sleep(0.5)
            continue
        try:
            yield _mjpeg_part(jpeg)
        except (asyncio.CancelledError, GeneratorExit):
            raise
        sent += 1
        await asyncio.sleep(_STREAM_INTERVAL_S)


@router.get("/stream")
async def camera_stream(camera: CameraSource = Depends(get_camera)) -> StreamingResponse:
    """Stream MJPEG (`multipart/x-mixed-replace`) para preview em tempo real."""
    return StreamingResponse(
        mjpeg_frames(camera),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )
