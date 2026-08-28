"""Endpoint de captura manual (TASK-001; fluxo real em TASK-004/TASK-009)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.models.result import CaptureResponse

router = APIRouter(prefix="/api", tags=["capture"])


@router.post("/capture", response_model=CaptureResponse, status_code=status.HTTP_202_ACCEPTED)
async def capture() -> CaptureResponse:
    """Dispara o pipeline de captura. Ligado ao `QuestionPipeline` na TASK-004."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Captura será implementada na TASK-004",
    )
