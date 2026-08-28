"""`HistoryStore` — histórico de questões resolvidas (TASK-014).

Opcional no MVP (`STORE_HISTORY`). Guarda **apenas** questão, resposta,
timestamps e métricas — nunca imagens (secção 19).

Implementação em memória (deque limitada). Trocar por SQLite só quando o
histórico tiver de sobreviver a um restart — não antes.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone

from app.models.result import ConsolidatedResponse

_MAX_ENTRIES = 100


class HistoryStore:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._entries: deque[dict] = deque(maxlen=_MAX_ENTRIES)
        self._lock = threading.Lock()

    def save(self, response: ConsolidatedResponse) -> None:
        if not self._enabled or response.status != "completed":
            return
        entry = {
            "id": response.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "question": response.question.model_dump(mode="json") if response.question else None,
            "result": response.result.model_dump(mode="json") if response.result else None,
            "timing": response.timing.model_dump(mode="json"),
        }
        with self._lock:
            self._entries.appendleft(entry)

    def list(self) -> list[dict]:
        with self._lock:
            return list(self._entries)

    def get(self, entry_id: str) -> dict | None:
        with self._lock:
            return next((e for e in self._entries if e["id"] == entry_id), None)

    def delete(self, entry_id: str) -> bool:
        with self._lock:
            for e in list(self._entries):
                if e["id"] == entry_id:
                    self._entries.remove(e)
                    return True
        return False
