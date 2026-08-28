"""`HistoryStore` — placeholder da TASK-001 (opcional no MVP).

Guarda apenas questão, resposta, timestamps e métricas — nunca imagens.
Backend SQLite só se necessário. Endpoints: TASK-019 (fora do MVP mínimo).
"""

from __future__ import annotations

from app.models.result import ConsolidatedResponse


class HistoryStore:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    async def save(self, response: ConsolidatedResponse) -> None:
        # No MVP a persistência é opcional; sem-op quando desligada.
        if not self._enabled:
            return
        raise NotImplementedError("Persistência de histórico: task futura")

    async def list(self) -> list[ConsolidatedResponse]:
        raise NotImplementedError("Persistência de histórico: task futura")
