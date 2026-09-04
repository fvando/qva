"""TASK-005 — ImageProcessor."""

import cv2
import numpy as np
import pytest

from app.vision.processor import (
    ImageProcessor,
    ImageQualityError,
    brightness,
    find_screen_quad,
    normalize_size,
    perspective_score,
    sharpness,
    warp_to_rect,
)


def _sharp_document(w=800, h=600) -> np.ndarray:
    """Imagem nítida: fundo claro com texto/linhas pretas de alto contraste."""
    img = np.full((h, w, 3), 240, dtype=np.uint8)
    for y in range(60, h - 60, 40):
        cv2.putText(img, "Questao " + str(y), (50, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    return img


def _screen_in_scene(w=1000, h=800) -> np.ndarray:
    """Cena com uma 'tela' retangular clara sobre fundo escuro."""
    img = np.full((h, w, 3), 30, dtype=np.uint8)
    doc = _sharp_document(600, 400)
    img[150 : 150 + 400, 200 : 200 + 600] = doc
    return img


# -- Métricas ---------------------------------------------------------------
def test_sharpness_blur_vs_sharp():
    sharp = _sharp_document()
    blurred = cv2.GaussianBlur(sharp, (21, 21), 0)
    g1 = cv2.cvtColor(sharp, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
    assert sharpness(g1) > sharpness(g2)


def test_brightness_range():
    dark = np.full((10, 10), 5, dtype=np.uint8)
    bright = np.full((10, 10), 250, dtype=np.uint8)
    assert brightness(dark) < 40
    assert brightness(bright) > 225


# -- Qualidade: falha cedo -----------------------------------------------
async def test_rejects_empty_frame():
    with pytest.raises(ImageQualityError) as e:
        await ImageProcessor().process(np.zeros((0, 0, 3), dtype=np.uint8))
    assert e.value.reason == "empty_frame"


async def test_rejects_blur():
    blurred = cv2.GaussianBlur(_sharp_document(), (25, 25), 0)
    with pytest.raises(ImageQualityError) as e:
        await ImageProcessor().process(blurred)
    assert e.value.reason == "blur_detected"


async def test_rejects_too_dark():
    dark = np.full((400, 400, 3), 10, dtype=np.uint8)
    # adiciona algum detalhe para não falhar primeiro por blur
    cv2.rectangle(dark, (50, 50), (350, 350), (30, 30, 30), 3)
    with pytest.raises(ImageQualityError) as e:
        await ImageProcessor(min_sharpness=0.0).process(dark)
    assert e.value.reason == "too_dark"


async def test_rejects_too_bright():
    white = np.full((400, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(white, (50, 50), (350, 350), (250, 250, 250), 3)
    with pytest.raises(ImageQualityError) as e:
        await ImageProcessor(min_sharpness=0.0).process(white)
    assert e.value.reason == "too_bright"


# -- Fluxo completo -----------------------------------------------------
async def test_process_plain_document_no_screen():
    result = await ImageProcessor().process(_sharp_document())
    assert result.image is not None
    assert result.sharpness_score > 0
    assert 40 <= result.brightness_score <= 248
    assert set(result.metrics()) == {
        "sharpness_score",
        "brightness_score",
        "perspective_score",
    }


async def test_process_detects_screen_and_warps():
    scene = _screen_in_scene()
    result = await ImageProcessor().process(scene)
    assert result.screen_detected is True
    assert result.perspective_score > 0
    # A imagem tratada deve aproximar-se do tamanho do 'documento' recortado,
    # não do tamanho da cena inteira.
    assert result.image.shape[0] < scene.shape[0]


# -- Funções isoladas -------------------------------------------------------
def test_find_screen_quad_returns_four_points():
    quad = find_screen_quad(cv2.cvtColor(_screen_in_scene(), cv2.COLOR_BGR2GRAY))
    assert quad is not None
    assert quad.shape == (4, 2)


def test_find_screen_quad_none_when_no_rectangle():
    noise = np.random.randint(0, 255, (300, 300), dtype=np.uint8)
    assert find_screen_quad(noise) is None


def test_perspective_score_zero_without_quad():
    assert perspective_score(None, (100, 100)) == 0.0


def test_warp_to_rect_output_shape():
    img = _sharp_document()
    quad = np.array([[10, 10], [700, 20], [690, 500], [20, 480]], dtype=np.float32)
    out = warp_to_rect(img, quad)
    assert out.ndim == 3 and out.shape[2] == 3


def test_normalize_size_never_upscales():
    small = np.zeros((100, 120, 3), dtype=np.uint8)
    assert normalize_size(small, max_side=1600).shape == (100, 120, 3)
    big = np.zeros((2000, 3000, 3), dtype=np.uint8)
    out = normalize_size(big, max_side=1600)
    assert max(out.shape[:2]) == 1600
