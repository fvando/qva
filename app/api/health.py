"""Health checks (TASK-001; camera real em TASK-002; llm em TASK-006)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.camera.base import CameraSource
from app.config import Settings, get_settings
from app.dependencies import get_camera

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    camera: CameraSource = Depends(get_camera),
) -> dict:
    camera_ok = await asyncio.to_thread(camera.is_available)
    return {
        "status": "healthy",
        "camera": camera_ok,
        "llm": None,  # verificação real: TASK-006
    }


@router.get("/api/llm/status")
async def llm_status(settings: Settings = Depends(get_settings)) -> dict:
    """Valida a ligação ao serviço LLM local. Implementação real: TASK-006."""
    return {
        "configured_url": settings.llm_url,
        "model": settings.llm_model,
        "supports_vision": settings.llm_supports_vision,
        "reachable": None,
    }
