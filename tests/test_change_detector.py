"""TASK-015 — ChangeDetector."""

import cv2
import numpy as np

from app.vision.change_detector import ChangeDetector, _dhash, _hash_distance


def _scene(seed: int, text: str = "") -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((300, 400, 3), 240, dtype=np.uint8)
    # muitos blocos coloridos determinísticos -> cenas visualmente distintas
    for _ in range(25):
        x, y = int(rng.integers(0, 350)), int(rng.integers(0, 250))
        color = tuple(int(c) for c in rng.integers(0, 200, 3))
        cv2.rectangle(img, (x, y), (x + 50, y + 50), color, -1)
    if text:
        cv2.putText(img, text, (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
    return img


def test_no_reference_means_everything_is_new():
    d = ChangeDetector()
    assert d.has_reference is False
    assert d.difference(_scene(1)) == 1.0
    assert d.is_new_question(_scene(1)) is True


def test_same_frame_is_not_new():
    d = ChangeDetector(threshold=0.25)
    frame = _scene(42)
    d.register(frame)
    assert d.difference(frame) < 0.05
    assert d.is_new_question(frame) is False


def test_small_noise_is_below_threshold():
    d = ChangeDetector(threshold=0.25)
    frame = _scene(7)
    d.register(frame)
    noise = np.random.default_rng(0).integers(-5, 6, frame.shape, dtype=np.int16)
    noisy = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    assert d.is_new_question(noisy) is False


def test_different_scene_is_new():
    d = ChangeDetector(threshold=0.25)
    d.register(_scene(1, "Questao A"))
    assert d.is_new_question(_scene(999, "Questao B")) is True


def test_register_updates_reference():
    d = ChangeDetector(threshold=0.25)
    a, b = _scene(1, "A"), _scene(2, "B")
    d.register(a)
    assert d.is_new_question(b) is True
    d.register(b)
    assert d.is_new_question(b) is False


def test_dhash_shape_and_distance():
    g = cv2.cvtColor(_scene(3), cv2.COLOR_BGR2GRAY)
    h = _dhash(g)
    assert h.shape == (8, 8)
    assert _hash_distance(h, h) == 0.0
    assert _hash_distance(h, ~h) == 1.0


def test_accepts_grayscale_input():
    d = ChangeDetector()
    gray = cv2.cvtColor(_scene(5), cv2.COLOR_BGR2GRAY)
    d.register(gray)
    assert d.is_new_question(gray) is False
