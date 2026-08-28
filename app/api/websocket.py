"""Endpoint WebSocket `WS /ws` (TASK-010).

O cliente liga-se e fica à escuta. Não precisa de enviar nada — o servidor
empurra os eventos do pipeline. Recebemos mensagens só para detetar a
desconexão (e ignoramos o conteúdo).
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
