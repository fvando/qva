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


def test_usb_close_releases_open_capture(monkeypatch):
    from app.camera.usb import USBCamera

    released = {"v": False}

    class FakeCap:
        def isOpened(self):
            return True

        def read(self):
            return True, np.zeros((2, 2, 3), dtype=np.uint8)

        def release(self):
            released["v"] = True

    monkeypatch.setattr("app.camera.usb.cv2.VideoCapture", lambda dev: FakeCap())
    cam = USBCamera("0")
    cam.open()
    cam.close()
    assert released["v"] is True


def test_context_manager_opens_and_closes(monkeypatch):
    from app.camera.usb import USBCamera

    events = []

    class FakeCap:
        def isOpened(self):
            return True

        def read(self):
            return True, np.zeros((2, 2, 3), dtype=np.uint8)

        def release(self):
            events.append("release")

    monkeypatch.setattr("app.camera.usb.cv2.VideoCapture", lambda dev: FakeCap())
    with USBCamera("0") as cam:
        cam.capture()
    assert "release" in events
