"""Health checks (TASK-001; `llm`/`camera` reais em TASK-002/TASK-006)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    """Estado global. Camera/LLM ficam `None` até as tasks respetivas ligarem
    verificações reais — nunca reportar `True` sem checar."""
    return {
        "status": "healthy",
        "camera": None,
        "llm": None,
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
