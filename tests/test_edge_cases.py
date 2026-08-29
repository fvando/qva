"""TASK-014 — lacunas de cobertura: encoding, json_utils, ocr, usb."""

import numpy as np
import pytest


def test_encoding_wraps_cv2_error(monkeypatch):
    import app.vision.encoding as enc

    def boom(*a, **k):
        raise enc.cv2.error("falhou")

    monkeypatch.setattr(enc.cv2, "imencode", boom)
    with pytest.raises(ValueError):
        enc.encode_jpeg(np.zeros((4, 4, 3), dtype=np.uint8))


def test_json_utils_empty_text():
    from app.llm.json_utils import JsonExtractionError, extract_json_object

    with pytest.raises(JsonExtractionError):
        extract_json_object("")


def test_json_utils_clamp01_non_numeric():
    from app.llm.json_utils import clamp01

    assert clamp01("abc") == 0.0
    assert clamp01(None) == 0.0
    assert clamp01(-3) == 0.0
    assert clamp01(9) == 1.0


def test_tesseract_ocr_missing_dependency(monkeypatch):
    import builtins

    from app.vision.ocr import OCRUnavailableError, TesseractOCR

    real_import = builtins.__import__

    def no_pytesseract(name, *a, **k):
        if name == "pytesseract":
            raise ImportError("sem pytesseract")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_pytesseract)
    with pytest.raises(OCRUnavailableError):
        TesseractOCR().image_to_text(np.zeros((4, 4, 3), dtype=np.uint8))


def test_build_ocr_engine_falls_back_and_raises(monkeypatch):
    import app.vision.ocr as ocr_mod
    from app.vision.ocr import OCRUnavailableError

    def unavailable(*a, **k):
        raise OCRUnavailableError("nada")

    monkeypatch.setattr(ocr_mod.RapidOCREngine, "__init__", unavailable)
    monkeypatch.setattr(ocr_mod.TesseractOCR, "__init__", unavailable)
    with pytest.raises(OCRUnavailableError):
        ocr_mod.build_ocr_engine()


def test_build_ocr_engine_picks_first_available(monkeypatch):
    import app.vision.ocr as ocr_mod

    monkeypatch.setattr(ocr_mod.RapidOCREngine, "__init__", lambda self: None)
    engine = ocr_mod.build_ocr_engine()
    assert isinstance(engine, ocr_mod.RapidOCREngine)


def _bright_cap(events=None):
    class FakeCap:
        def isOpened(self):
            return True

        def read(self):
            return True, np.full((4, 4, 3), 200, dtype=np.uint8)

        def set(self, *a):
            pass

        def release(self):
            if events is not None:
                events.append("release")

    return FakeCap()


def test_usb_close_releases_open_capture(monkeypatch):
    from app.camera.usb import USBCamera

    events = []
    monkeypatch.setattr(
        "app.camera.usb.cv2.VideoCapture", lambda dev, backend=None: _bright_cap(events)
    )
    cam = USBCamera("0")
    cam.open()
    cam.close()
    assert "release" in events


def test_context_manager_opens_and_closes(monkeypatch):
    from app.camera.usb import USBCamera

    events = []
    monkeypatch.setattr(
        "app.camera.usb.cv2.VideoCapture", lambda dev, backend=None: _bright_cap(events)
    )
    with USBCamera("0") as cam:
        cam.capture()
    assert "release" in events
