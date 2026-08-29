"""Endpoints de captura (TASK-004) — simples e multi-página.

`POST /api/capture` responde de imediato com um `capture_id` e processa em
background. Para questões que ocupam mais de um ecrã: `POST /api/capture/page`
(uma por página) + `POST /api/capture/solve`.
"""

from __future__ import annotations

import asyncio

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from app.dependencies import (
    get_camera,
    get_capture_registry,
    get_image_processor,
    get_page_buffer,
    get_pipeline,
)
from app.camera.base import CameraError, CameraSource
from app.models.result import CaptureResponse, ConsolidatedResponse
from app.services.captures import CaptureRegistry
from app.services.pages import PageBuffer
from app.services.pipeline import QuestionPipeline
from app.vision.processor import ImageProcessor, ImageQualityError

router = APIRouter(prefix="/api", tags=["capture"])


@router.post(
    "/capture",
    response_model=CaptureResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def capture(
    background: BackgroundTasks,
    pipeline: QuestionPipeline = Depends(get_pipeline),
    registry: CaptureRegistry = Depends(get_capture_registry),
    pages: PageBuffer = Depends(get_page_buffer),
) -> CaptureResponse:
    pages.clear()  # uma captura simples cancela um multi-página a meio
    job = registry.create()
    background.add_task(pipeline.process_capture, job.id)
    return CaptureResponse(capture_id=job.id, status="processing")


# -- multi-página (rotas estáticas ANTES da paramétrica /capture/{id}) --
async def _grab_and_process(
    camera: CameraSource, processor: ImageProcessor, frame_jpeg: bytes | None
):
    def _work():
        if frame_jpeg is not None:
            import cv2
            import numpy as np

            arr = np.frombuffer(frame_jpeg, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                raise CameraError("frame enviado não é um JPEG válido")
        else:
            camera.open()
            img = camera.capture()
        return processor.process_sync(img)

    return await asyncio.to_thread(_work)


@router.post("/capture/page")
async def add_page(
    request: Request,
    camera: CameraSource = Depends(get_camera),
    processor: ImageProcessor = Depends(get_image_processor),
    pages: PageBuffer = Depends(get_page_buffer),
) -> dict:
    """Captura (ou recebe) uma página e acumula-a. Content-Type image/jpeg para
    enviar o frame do browser; corpo vazio para a câmera do servidor."""
    body = await request.body()
    frame_jpeg = body or None
    try:
        processed = await _grab_and_process(camera, processor, frame_jpeg)
    except (CameraError, ImageQualityError) as exc:
        detail = getattr(exc, "reason", str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    try:
        total = pages.add(processed)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"pages": total}


@router.get("/capture/pages")
async def page_count(pages: PageBuffer = Depends(get_page_buffer)) -> dict:
    return {"pages": pages.count}


@router.delete("/capture/pages")
async def clear_pages(pages: PageBuffer = Depends(get_page_buffer)) -> Response:
    pages.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/capture/solve",
    response_model=CaptureResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def solve_pages(
    background: BackgroundTasks,
    pipeline: QuestionPipeline = Depends(get_pipeline),
    registry: CaptureRegistry = Depends(get_capture_registry),
    pages: PageBuffer = Depends(get_page_buffer),
) -> CaptureResponse:
    collected = pages.take_all()
    if not collected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="nenhuma página adicionada — usa POST /api/capture/page primeiro",
        )
    job = registry.create()
    background.add_task(pipeline.process_capture, job.id, pages=collected)
    return CaptureResponse(capture_id=job.id, status="processing")


# -- paramétrica: DEPOIS das rotas /capture/page|pages|solve ---------
@router.get("/capture/{capture_id}", response_model=ConsolidatedResponse)
async def capture_status(
    capture_id: str,
    registry: CaptureRegistry = Depends(get_capture_registry),
) -> ConsolidatedResponse:
    job = registry.get(capture_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="capture_id desconhecido"
        )
    if job.response is not None:
        return job.response
    return ConsolidatedResponse(id=job.id, status=job.state.value, error=job.error)
