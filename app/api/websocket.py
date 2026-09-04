"""Endpoint WebSocket `WS /ws` + reenvio da última resposta (TASK-010).

O cliente liga-se e fica à escuta — ao ligar recebe já o último resultado
(se houver), para a app de consulta que chega atrasada não perder nada.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.dependencies import get_websocket_manager
from app.websocket_manager import WebSocketManager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def ws(
    websocket: WebSocket,
    manager: WebSocketManager = Depends(get_websocket_manager),
) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Mantém a ligação viva; qualquer mensagem do cliente é ignorada.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:  # noqa: BLE001 - garante a limpeza em qualquer falha
        await manager.disconnect(websocket)


@router.post("/api/answer/resend", tags=["answer"])
async def resend_last_answer(
    manager: WebSocketManager = Depends(get_websocket_manager),
) -> dict:
    """Reenvia a última resposta a todos os clientes ligados — útil quando a
    app de consulta se ligou depois da captura ou perdeu a mensagem."""
    sent = await manager.resend_last()
    return {"resent": sent}
