"""Health checks + estado/escolha do modelo LLM."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.camera.base import CameraSource
from app.config import Settings, get_settings
from app.dependencies import get_camera, get_llm_client
from app.llm.base import LLMClient
from app.llm.http_client import HttpLLMClient

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
    return {"status": "healthy", "camera": camera_ok, "llm": llm_ok}


@router.get("/api/llm/status")
async def llm_status(
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm_client),
) -> dict:
    reachable = await llm.health()
    model = llm.model if isinstance(llm, HttpLLMClient) else settings.llm_model
    is_cloud = settings.llm_base_url.startswith("https://") and "localhost" not in settings.llm_base_url
    return {
        "configured_url": settings.llm_url,
        "model": model,
        "mode": settings.llm_mode,
        "supports_vision": settings.llm_supports_vision,
        "cloud": is_cloud,
        "reachable": reachable,
    }


def _allowed_models(settings: Settings) -> set[str] | None:
    raw = settings.llm_models_allowed.strip()
    if not raw:
        return None
    return {m.strip() for m in raw.split(",") if m.strip()}


@router.get("/api/llm/models")
async def llm_models(
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm_client),
) -> dict:
    """Modelos que a UI pode oferecer.

    Interseção dos modelos que o serviço expõe com `LLM_MODELS_ALLOWED` (se
    definido). O modelo ativo é sempre incluído.
    """
    active = llm.model if isinstance(llm, HttpLLMClient) else settings.llm_model

    allowed = _allowed_models(settings)
    if allowed is not None:
        # Allowlist explícita — não sondar o serviço (pode ter centenas).
        chosen = sorted(allowed)
    else:
        available = []
        if isinstance(llm, HttpLLMClient):
            available = await llm.list_models()
        # Muitos serviços cloud expõem centenas de modelos — não faz sentido
        # numa dropdown. Só listamos se forem poucos.
        chosen = available if 0 < len(available) <= 40 else []

    if active and active not in chosen:
        chosen = [active, *chosen]
    return {"active": active, "models": chosen}


class SelectModelBody(BaseModel):
    model: str


@router.post("/api/llm/select")
async def llm_select(
    body: SelectModelBody,
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm_client),
) -> dict:
    if not isinstance(llm, HttpLLMClient):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="o cliente LLM atual não suporta troca de modelo",
        )
    name = body.model.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="modelo vazio")

    allowed = _allowed_models(settings)
    if allowed is not None and name not in allowed:
        # Ainda aceitamos se o serviço realmente o tem — a allowlist é só o
        # conjunto "sugerido" para a UI, não uma barreira de segurança.
        available = await llm.list_models()
        if name not in available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"modelo '{name}' não disponível",
            )

    llm.set_model(name)
    return {"active": name}
