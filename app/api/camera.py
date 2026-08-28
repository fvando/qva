"""Endpoints da câmera (TASK-001; status real em TASK-002; preview em TASK-003)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.camera.base import CameraSource
from app.config import Settings, get_settings
from app.dependencies import get_camera

router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/status")
async def camera_status(
    settings: Settings = Depends(get_settings),
    camera: CameraSource = Depends(get_camera),
) -> dict:
    # `is_available()` toca em I/O de hardware — nunca no event loop.
    available = await asyncio.to_thread(camera.is_available)
    return {
        "available": available,
        "type": settings.camera_type.value,
        "device": settings.camera_device,
    }
