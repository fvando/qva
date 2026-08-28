"""`ImageProcessor` — tratamento de imagem e métricas de qualidade (TASK-005).

Fluxo: valida nitidez/brilho → deteta a região retangular da tela → corrige a
perspetiva (warp para retângulo frontal) → deskew fino → melhora contraste
(CLAHE) → normaliza o tamanho. Tudo em memória, sem `cv2.imwrite`.

As operações de OpenCV são síncronas e pesadas; quem chama (`QuestionPipeline`)
deve executá-las via `asyncio.to_thread`. `process()` é `async` só para manter
o contrato do pipeline — internamente delega para `process_sync`.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# -- Limiares de qualidade (ajustáveis; começam conservadores) --------------
# Variância do Laplaciano: abaixo disto a imagem está desfocada.
MIN_SHARPNESS = 60.0
# Brilho médio (0-255): fora deste intervalo está escura/queimada demais.
# O limite superior é alto de propósito — um documento/tela bem iluminado tem
# fundo perto do branco; só rejeitamos quando está mesmo "estourado".
MIN_BRIGHTNESS = 40.0
MAX_BRIGHTNESS = 248.0
# Lado alvo (px) da imagem normalizada entregue ao extractor.
TARGET_MAX_SIDE = 1600


@dataclass
class ProcessedImage:
    """Imagem tratada + métricas de qualidade.

    `image` é um `np.ndarray` BGR. `screen_detected` diz se foi encontrada uma
    região retangular de tela (e portanto se houve correção de perspetiva) ou
    se se usou o frame inteiro.
    """

    image: np.ndarray
    sharpness_score: float = 0.0
    brightness_score: float = 0.0
    perspective_score: float = 0.0
    screen_detected: bool = False

    def metrics(self) -> dict[str, float]:
        return {
            "sharpness_score": round(self.sharpness_score, 2),
            "brightness_score": round(self.brightness_score, 2),
            "perspective_score": round(self.perspective_score, 3),
        }


class ImageQualityError(RuntimeError):
    """Imagem imprópria para interpretação (blur, brilho, perspetiva).

    `reason` usa códigos estáveis: `blur_detected`, `too_dark`, `too_bright`,
    `empty_frame`.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------
def sharpness(gray: np.ndarray) -> float:
    """Variância do Laplaciano — quanto maior, mais nítida a imagem."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def brightness(gray: np.ndarray) -> float:
    """Brilho médio (0-255)."""
    return float(gray.mean())


# --------------------------------------------------------------------------
# Deteção da tela + correção de perspetiva
# --------------------------------------------------------------------------
def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Ordena 4 pontos como [topo-esq, topo-dir, baixo-dir, baixo-esq]."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect


def find_screen_quad(gray: np.ndarray) -> np.ndarray | None:
    """Procura o maior contorno de 4 lados que possa ser a tela.

    Devolve os 4 cantos (float32) ou `None` se não houver candidato razoável.
    """
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    h, w = gray.shape[:2]
    img_area = h * w
    margin = 3  # px — cantos colados à borda = moldura do frame, não a tela
    best: np.ndarray | None = None
    best_area = 0.0
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        area = cv2.contourArea(c)
        # Ignora contornos minúsculos (< 15%) e o frame quase inteiro (> 98%).
        if area < 0.15 * img_area or area > 0.98 * img_area:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        pts = approx.reshape(4, 2).astype(np.float32)
        # Rejeita se todos os cantos estão encostados às bordas da imagem.
        on_border = np.all(
            (pts[:, 0] <= margin)
            | (pts[:, 0] >= w - 1 - margin)
            | (pts[:, 1] <= margin)
            | (pts[:, 1] >= h - 1 - margin)
        )
        if on_border:
            continue
        if area > best_area:
            best = pts
            best_area = area
    return best


def warp_to_rect(image: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Corrige a perspetiva: mapeia o quadrilátero para um retângulo frontal."""
    rect = _order_corners(quad)
    (tl, tr, br, bl) = rect
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    width = max(width, 1)
    height = max(height, 1)
    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    m = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, m, (width, height))


def perspective_score(quad: np.ndarray | None, image_shape: tuple[int, int]) -> float:
    """0.0 = sem tela detetada; ~1.0 = tela ocupa e alinha bem com o frame.

    Combina a fração de área ocupada com o quão "retangular" é o quadrilátero.
    """
    if quad is None:
        return 0.0
    h, w = image_shape[:2]
    area_frac = min(cv2.contourArea(quad.astype(np.float32)) / (h * w), 1.0)
    rect = _order_corners(quad)
    top = np.linalg.norm(rect[1] - rect[0])
    bottom = np.linalg.norm(rect[2] - rect[3])
    left = np.linalg.norm(rect[3] - rect[0])
    right = np.linalg.norm(rect[2] - rect[1])
    # Quão simétricos são os lados opostos (1.0 = retângulo perfeito).
    h_sym = min(top, bottom) / max(top, bottom, 1e-6)
    v_sym = min(left, right) / max(left, right, 1e-6)
    return float(area_frac * (h_sym + v_sym) / 2)


# --------------------------------------------------------------------------
# Melhoria de imagem
# --------------------------------------------------------------------------
def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """CLAHE no canal de luminância (LAB) — realça texto sem estourar cores."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def deskew(image: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """Corrige pequenas inclinações (< ~10°) por linhas de Hough."""
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=150)
    if lines is None:
        return image
    angles = []
    for rho_theta in lines[:50]:
        theta = rho_theta[0][1]
        deg = np.degrees(theta) - 90
        if -10 < deg < 10:
            angles.append(deg)
    if not angles:
        return image
    angle = float(np.median(angles))
    h, w = image.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        image, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def normalize_size(image: np.ndarray, max_side: int = TARGET_MAX_SIDE) -> np.ndarray:
    """Reduz a imagem se o maior lado exceder `max_side` (nunca amplia)."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image
    scale = max_side / longest
    return cv2.resize(
        image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
    )


class ImageProcessor:
    """Trata um frame BGR e devolve `ProcessedImage` com métricas.

    Levanta `ImageQualityError` se a imagem for imprópria (blur / brilho).
    """

    def __init__(
        self,
        min_sharpness: float = MIN_SHARPNESS,
        min_brightness: float = MIN_BRIGHTNESS,
        max_brightness: float = MAX_BRIGHTNESS,
    ) -> None:
        self._min_sharpness = min_sharpness
        self._min_brightness = min_brightness
        self._max_brightness = max_brightness

    async def process(self, frame: np.ndarray) -> ProcessedImage:
        """Versão async por conveniência. O pipeline usa `process_sync` dentro
        de `asyncio.to_thread` para não bloquear o event loop."""
        return self.process_sync(frame)

    def process_sync(self, frame: np.ndarray) -> ProcessedImage:
        if frame is None or getattr(frame, "size", 0) == 0:
            raise ImageQualityError("empty_frame")

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. Validação de qualidade (falha cedo) --------------------------
        sharp = sharpness(gray)
        bright = brightness(gray)
        if sharp < self._min_sharpness:
            raise ImageQualityError("blur_detected")
        if bright < self._min_brightness:
            raise ImageQualityError("too_dark")
        if bright > self._max_brightness:
            raise ImageQualityError("too_bright")

        # 2. Deteção da tela + correção de perspetiva ----------------
        quad = find_screen_quad(gray)
        persp = perspective_score(quad, frame.shape)
        if quad is not None:
            work = warp_to_rect(frame, quad)
            screen_detected = True
        else:
            work = frame.copy()
            screen_detected = False

        # 3. Deskew + contraste + normalização -----------------------
        work_gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
        work = deskew(work, work_gray)
        work = enhance_contrast(work)
        work = normalize_size(work)

        return ProcessedImage(
            image=work,
            sharpness_score=sharp,
            brightness_score=bright,
            perspective_score=persp,
            screen_detected=screen_detected,
        )
