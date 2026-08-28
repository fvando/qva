"""Endpoint de captura manual (TASK-004).

Responde de imediato com um `capture_id` e processa em background. Toda a
lógica vive no `QuestionPipeline` — o endpoint só regista a captura, agenda a
tarefa e devolve o identificador.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.dependencies import get_capture_registry, get_pipeline
from app.models.result import CaptureResponse, ConsolidatedResponse
from app.services.captures import CaptureRegistry
from app.services.pipeline import QuestionPipeline

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
) -> CaptureResponse:
    job = registry.create()
    background.add_task(pipeline.process_capture, job.id)
    return CaptureResponse(capture_id=job.id, status="processing")


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
    # Ainda em processamento (ou falhou sem resposta consolidada).
    return ConsolidatedResponse(
        id=job.id,
        status=job.state.value,
        error=job.error,
    )
