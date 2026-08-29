"""Gera os ícones da PWA (executar uma vez, ou quando o design mudar).

    python app/static/make_icons.py

Produz icon-192.png, icon-512.png e icon-maskable-512.png a partir de um
desenho vetorial simples: uma "lente" (câmera) sobre o azul da marca.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).parent
BG = (226, 88, 37)  # #2563eb em BGR
FG = (255, 255, 255)


def _draw(size: int, maskable: bool) -> np.ndarray:
    img = np.full((size, size, 3), BG, dtype=np.uint8)
    c = size // 2
    # margem de segurança maior para ícones "maskable" (o SO recorta os cantos)
    r_outer = int(size * (0.30 if maskable else 0.34))
    r_inner = int(size * (0.17 if maskable else 0.19))

    cv2.circle(img, (c, c), r_outer, FG, thickness=max(2, size // 40), lineType=cv2.LINE_AA)
    cv2.circle(img, (c, c), r_inner, FG, thickness=-1, lineType=cv2.LINE_AA)
    # reflexo
    cv2.circle(
        img,
        (c - r_inner // 3, c - r_inner // 3),
        max(2, r_inner // 4),
        BG,
        thickness=-1,
        lineType=cv2.LINE_AA,
    )
    return img


def _save(img: np.ndarray, name: str) -> None:
    path = OUT / name
    path.write_bytes(cv2.imencode(".png", img)[1].tobytes())
    print("escrito:", path)


if __name__ == "__main__":
    _save(_draw(192, maskable=False), "icon-192.png")
    _save(_draw(512, maskable=False), "icon-512.png")
    _save(_draw(512, maskable=True), "icon-maskable-512.png")
