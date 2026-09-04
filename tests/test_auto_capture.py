"""TASK-016 — captura automática opcional."""

import asyncio

import cv2
import numpy as np

from app.config import Settings
from app.services.auto_capture import AutoCaptureLoop
from app.services.captures import CaptureRegistry
from app.vision.change_detector import ChangeDetector
from tests.conftest import FakeCamera


class ScriptedCamera(FakeCamera):
    """Devolve uma sequência de frames, repetindo o último."""

    def __init__(self, frames: list[np.ndarray]) -> None:
        super().__init__()
        self._frames = frames
        self._i = 0

    def capture(self) -> np.ndarray:
        frame = self._frames[min(self._i, len(self._frames) - 1)]
        self._i += 1
        return frame.copy()


class RecordingPipeline:
    def __init__(self) -> None:
        self.calls: list = []

    async def process_capture(self, capture_id, *, frame=None):
        self.calls.append((capture_id, frame))


def _scene(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((200, 300, 3), 240, dtype=np.uint8)
    for _ in range(25):
        x, y = int(rng.integers(0, 250)), int(rng.integers(0, 150))
        c = tuple(int(v) for v in rng.integers(0, 200, 3))
        cv2.rectangle(img, (x, y), (x + 40, y + 40), c, -1)
    return img


def _settings(**over) -> Settings:
    base = dict(
        _env_file=None,
        auto_capture_enabled=True,
        change_threshold=0.25,
        stabilization_ms=400,
    )
    base.update(over)
    return Settings(**base)


def test_disabled_loop_does_not_start():
    loop = AutoCaptureLoop(
        settings=_settings(auto_capture_enabled=False),
        camera=FakeCamera(),
        detector=ChangeDetector(),
        pipeline=RecordingPipeline(),
        registry=CaptureRegistry(),
    )
    loop.start()
    assert loop.is_running is False


async def test_triggers_pipeline_on_stable_change():
    a, b = _scene(1), _scene(2)
    # frame inicial 'a' (referência), depois muda para 'b' e estabiliza em 'b'
    camera = ScriptedCamera([a, b, b, b, b, b, b, b, b, b])
    detector = ChangeDetector(threshold=0.25)
    detector.register(a)  # 'a' já é a referência
    pipeline = RecordingPipeline()

    loop = AutoCaptureLoop(
        settings=_settings(stabilization_ms=50),
        camera=camera,
        detector=detector,
        pipeline=pipeline,
        registry=CaptureRegistry(),
        poll_interval_s=0.01,
    )
    loop.start()
    # dá tempo ao loop de detetar + estabilizar + disparar


    for _ in range(200):
        await asyncio.sleep(0.01)
        if pipeline.calls:
            break
    await loop.stop()

    assert len(pipeline.calls) >= 1
    _, frame = pipeline.calls[0]
    assert frame is not None  # disparou com o frame estável observado


async def test_no_trigger_when_scene_static():
    a = _scene(7)
    camera = ScriptedCamera([a] * 20)
    detector = ChangeDetector(threshold=0.25)
    detector.register(a)
    pipeline = RecordingPipeline()

    loop = AutoCaptureLoop(
        settings=_settings(),
        camera=camera,
        detector=detector,
        pipeline=pipeline,
        registry=CaptureRegistry(),
        poll_interval_s=0.01,
    )
    loop.start()


    await asyncio.sleep(0.3)
    await loop.stop()

    assert pipeline.calls == []


async def test_stop_is_idempotent():
    loop = AutoCaptureLoop(
        settings=_settings(),
        camera=ScriptedCamera([_scene(1)] * 5),
        detector=ChangeDetector(),
        pipeline=RecordingPipeline(),
        registry=CaptureRegistry(),
        poll_interval_s=0.01,
    )
    loop.start()
    await loop.stop()
    await loop.stop()
    assert loop.is_running is False
