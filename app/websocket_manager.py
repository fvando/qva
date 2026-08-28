"""`WebSocketManager` — placeholder da TASK-001, implementado na TASK-010.

Mantém as ligações WebSocket ativas e faz broadcast dos eventos do pipeline
(`capture_started`, `question_detected`, `answer_ready`, `error`) para que o
telemóvel receba a resposta sem polling.
"""

from __future__ import annotations

from typing import Any


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: list[Any] = []

    async def connect(self, websocket: Any) -> None:  # pragma: no cover - TASK-010
        raise NotImplementedError("WebSocketManager será implementado na TASK-010")

    def disconnect(self, websocket: Any) -> None:  # pragma: no cover - TASK-010
        raise NotImplementedError("WebSocketManager será implementado na TASK-010")

    async def broadcast(
        self, event: str, data: dict | None = None
    ) -> None:  # pragma: no cover - TASK-010
        raise NotImplementedError("WebSocketManager será implementado na TASK-010")
