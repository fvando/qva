"""Endpoints da câmera (TASK-001; preview real em TASK-003)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/status")
async def camera_status(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "available": None,  # verificação real: TASK-002
        "type": settings.camera_type.value,
        "device": settings.camera_device,
    }
