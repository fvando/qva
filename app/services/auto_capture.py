"""Captura automática opcional (TASK-016).

Quando `AUTO_CAPTURE_ENABLED=true`, um loop de background observa a câmera e
dispara o pipeline sozinho quando deteta uma questão nova e estável:

    lê frame
    -> ChangeDetector: mudou face à referência?
        não  -> continua
        sim  -> aguarda estabilização (frames seguidos sem mais mudança)
             -> dispara o pipeline
             -> regista o frame como nova referência (evita re-disparar)

Desligado por omissão. O loop é totalmente independente do endpoint
`POST /api/capture` (captura manual continua a funcionar em paralelo).
"""

from __future__ import annotations

import asyncio
import logging

from app.camera.base import CameraError, CameraSource
from app.config import Settings
from app.services.captures import CaptureRegistry
from app.services.pipeline import QuestionPipeline
from app.vision.change_detector import ChangeDetector

logger = logging.getLogger(__name__)

# Intervalo entre leituras de frame no loop de observação.
_POLL_INTERVAL_S = 0.4


class AutoCaptureLoop:
    def __init__(
        self,
        settings: Settings,
        camera: CameraSource,
        detector: ChangeDetector,
        pipeline: QuestionPipeline,
        registry: CaptureRegistry,
        *,
        poll_interval_s: float = _POLL_INTERVAL_S,
    ) -> None:
        self._settings = settings
        self._camera = camera
        self._detector = detector
        self._pipeline = pipeline
        self._registry = registry
        self._poll = poll_interval_s
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running or not self._settings.auto_capture_enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("AUTO_CAPTURE_STARTED")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("AUTO_CAPTURE_STOPPED")

    # -- loop -----------------------------------------------------------
    async def _run(self) -> None:
        stabilization_s = self._settings.stabilization_ms / 1000
        try:
            while self._running:
                await asyncio.sleep(self._poll)
                frame = await self._safe_grab()
                if frame is None:
                    continue

                if not self._detector.is_new_question(frame):
                    continue

                logger.info("AUTO_CAPTURE_CHANGE_DETECTED")
                stable = await self._wait_stable(stabilization_s)
                if stable is None:
                    continue  # não estabilizou; espera a próxima mudança

                self._detector.register(stable)
                await self._trigger(stable)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - o loop nunca deve morrer por um erro
            logger.exception("AUTO_CAPTURE_LOOP_ERROR")

    async def _wait_stable(self, stabilization_s: float):
        """Espera que a cena pare de mudar durante `stabilization_s` seguidos.

        Devolve o frame estável, ou `None` se voltar a mudar ou a câmera falhar.
        """
        checks = max(1, int(stabilization_s / self._poll))
        probe = ChangeDetector(threshold=self._settings.change_threshold)

        last = await self._safe_grab()
        if last is None:
            return None

        for _ in range(checks):
            await asyncio.sleep(self._poll)
            current = await self._safe_grab()
            if current is None:
                return None
            probe.register(last)
            if probe.is_new_question(current):
                return None  # ainda a mexer -> não é estável
            last = current
        return last

    async def _trigger(self, frame) -> None:
        """Dispara o pipeline com o frame estável já observado."""
        job = self._registry.create()
        logger.info("AUTO_CAPTURE_TRIGGER", extra={"capture_id": job.id})
        await self._pipeline.process_capture(job.id, frame=frame)

    async def _safe_grab(self):
        def _work():
            self._camera.open()
            return self._camera.capture()

        try:
            return await asyncio.to_thread(_work)
        except CameraError:
            return None
