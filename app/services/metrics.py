"""Métricas de latência agregadas (TASK-013).

O `Timing` por captura já é medido no pipeline (secção 21). Este módulo acumula
esses tempos em memória (local-first, sem BD) para dar uma visão agregada:
contagem, taxa de sucesso e latências (média / p50 / p95) por passo.

Guarda apenas números — nunca questões, respostas ou imagens.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field

from app.models.result import Timing

# Nº de capturas recentes mantidas para o cálculo de percentis.
_WINDOW = 200

_STEPS = (
    "capture_ms",
    "image_processing_ms",
    "question_extraction_ms",
    "llm_ms",
    "total_ms",
)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


@dataclass
class MetricsCollector:
    total: int = 0
    completed: int = 0
    errors: int = 0
    _samples: dict[str, deque] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        for step in _STEPS:
            self._samples[step] = deque(maxlen=_WINDOW)

    def record(self, timing: Timing, *, ok: bool) -> None:
        with self._lock:
            self.total += 1
            if ok:
                self.completed += 1
            else:
                self.errors += 1
            for step in _STEPS:
                self._samples[step].append(float(getattr(timing, step)))

    def snapshot(self) -> dict:
        with self._lock:
            steps = {}
            for step, samples in self._samples.items():
                vals = list(samples)
                steps[step] = {
                    "count": len(vals),
                    "avg_ms": round(sum(vals) / len(vals), 1) if vals else 0.0,
                    "p50_ms": round(_percentile(vals, 0.50), 1),
                    "p95_ms": round(_percentile(vals, 0.95), 1),
                }
            success_rate = round(self.completed / self.total, 3) if self.total else None
            return {
                "captures_total": self.total,
                "captures_completed": self.completed,
                "captures_error": self.errors,
                "success_rate": success_rate,
                "window": _WINDOW,
                "steps_ms": steps,
            }

    def reset(self) -> None:
        with self._lock:
            self.total = self.completed = self.errors = 0
            for step in _STEPS:
                self._samples[step].clear()
