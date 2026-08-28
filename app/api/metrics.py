"""Endpoint de métricas de latência agregadas (TASK-013)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_metrics
from app.services.metrics import MetricsCollector

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
async def metrics(collector: MetricsCollector = Depends(get_metrics)) -> dict:
    """Contagem de capturas, taxa de sucesso e latências (avg/p50/p95) por passo,
    sobre uma janela deslizante das capturas mais recentes. Só números."""
    return collector.snapshot()
