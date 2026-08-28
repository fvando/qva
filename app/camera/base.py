"""Interface `CameraSource` (TASK-001; implementações em TASK-002+).

Regra arquitetural: o `QuestionPipeline` só conhece esta interface. Trocar
USB por RTSP (fase 2) não deve exigir qualquer alteração no pipeline.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

# Um frame é sempre um array numpy BGR (convenção OpenCV), nunca um ficheiro.
Frame = "np.ndarray"


class CameraSource(abc.ABC):
    """Fonte de imagem abstrata."""

    @abc.abstractmethod
    def open(self) -> None:
        """Adquire o recurso da câmera. Idempotente."""

    @abc.abstractmethod
    def capture(self) -> "np.ndarray":
        """Devolve um único frame (array BGR em memória).

        Levanta `CameraError` se a câmera não estiver disponível.
        """

    @abc.abstractmethod
    def close(self) -> None:
        """Liberta o recurso. Idempotente."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """`True` se `capture()` deve conseguir devolver um frame agora."""

    def __enter__(self) -> "CameraSource":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class CameraError(RuntimeError):
    """Falha ao abrir ou capturar da câmera."""
