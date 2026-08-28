"""Health checks (camera real em TASK-002; llm real em TASK-006)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from app.camera.base import CameraSource
from app.config import Settings, get_settings
from app.dependencies import get_camera, get_llm_client
from app.llm.base import LLMClient

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    camera: CameraSource = Depends(get_camera),
    llm: LLMClient = Depends(get_llm_client),
) -> dict:
    camera_ok, llm_ok = await asyncio.gather(
        asyncio.to_thread(camera.is_available),
        llm.health(),
    )
    return {
        "status": "healthy",
        "camera": camera_ok,
        "llm": llm_ok,
    }


@router.get("/api/llm/status")
async def llm_status(
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm_client),
) -> dict:
    reachable = await llm.health()
    return {
        "configured_url": settings.llm_url,
        "model": settings.llm_model,
        "supports_vision": settings.llm_supports_vision,
        "reachable": reachable,
    }
