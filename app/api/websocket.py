"""Endpoint WebSocket (TASK-001; implementado na TASK-010)."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    """Canal de eventos em tempo real. Implementação real: TASK-010."""
    await websocket.accept()
    await websocket.send_json({"event": "error", "data": {"reason": "not_implemented"}})
    await websocket.close()
