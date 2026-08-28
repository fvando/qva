"""`WebSocketManager` — canal de eventos em tempo real (TASK-010).

Mantém o conjunto de ligações WebSocket ativas e faz broadcast dos eventos do
pipeline. O telemóvel recebe `answer_ready` sem fazer polling.

Eventos (secção 15 do prompt):
  capture_started | question_detected | answer_ready | error
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class WebSocketLike(Protocol):
    async def accept(self) -> None: ...
    async def send_json(self, data: Any) -> None: ...


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocketLike] = set()
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocketLike) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("WS_CONNECT", extra={"model": str(self.connection_count)})

    async def disconnect(self, websocket: WebSocketLike) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("WS_DISCONNECT", extra={"model": str(self.connection_count)})

    async def broadcast(self, event: str, data: dict | None = None) -> None:
        """Envia `{"event": ..., "data": ...}` a todas as ligações.

        Ligações que falharem o envio são removidas — um cliente morto nunca
        deve bloquear os restantes nem o pipeline.
        """
        message = {"event": event, "data": data or {}}
        async with self._lock:
            targets = list(self._connections)

        dead: list[WebSocketLike] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - qualquer falha = ligação perdida
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)
            logger.info("WS_PRUNED", extra={"model": str(len(dead))})
