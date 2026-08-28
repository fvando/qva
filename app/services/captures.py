"""Registo de capturas em curso (TASK-004).

`POST /api/capture` responde imediatamente com um `capture_id` e o processamento
segue em background. Este módulo guarda o estado de cada captura em memória
(dict simples — sem imagens, local-first) para que a UI e o WebSocket possam
consultar o progresso.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.models.result import ConsolidatedResponse


class CaptureState(str, Enum):
    """Estados visuais do pipeline (secção 17 do prompt)."""

    IDLE = "idle"
    CAPTURING = "capturing"
    PROCESSING_IMAGE = "processing_image"
    EXTRACTING_QUESTION = "extracting_question"
    SOLVING = "solving"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class CaptureJob:
    id: str
    state: CaptureState = CaptureState.CAPTURING
    response: ConsolidatedResponse | None = None
    error: str | None = None


class CaptureRegistry:
    """Guarda o estado das capturas. Um por processo (ver `dependencies.py`)."""

    def __init__(self) -> None:
        self._jobs: dict[str, CaptureJob] = {}

    def create(self) -> CaptureJob:
        job = CaptureJob(id=str(uuid.uuid4()))
        self._jobs[job.id] = job
        return job

    def get(self, capture_id: str) -> CaptureJob | None:
        return self._jobs.get(capture_id)

    def set_state(self, capture_id: str, state: CaptureState) -> None:
        job = self._jobs.get(capture_id)
        if job is not None:
            job.state = state

    def complete(self, capture_id: str, response: ConsolidatedResponse) -> None:
        job = self._jobs.get(capture_id)
        if job is not None:
            job.state = CaptureState.COMPLETED
            job.response = response

    def fail(self, capture_id: str, error: str) -> None:
        job = self._jobs.get(capture_id)
        if job is not None:
            job.state = CaptureState.ERROR
            job.error = error
