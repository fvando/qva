"""Gera a imagem fixture de questão usada pelos testes (executar uma vez).

    python tests/fixtures/make_fixture.py

Produz `question.jpg` — uma questão de múltipla escolha sintética, nítida e
legível, sem qualquer conteúdo real.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).parent / "question.jpg"


def build() -> np.ndarray:
    img = np.full((900, 1200, 3), 245, dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    black = (20, 20, 20)

    lines = [
        (60, "Qual estrutura de dados segue a politica LIFO?", 0.9, 2),
        (160, "A) Fila", 0.8, 2),
        (220, "B) Pilha", 0.8, 2),
        (280, "C) Arvore binaria", 0.8, 2),
        (340, "D) Lista ligada", 0.8, 2),
    ]
    for y, text, scale, thick in lines:
        cv2.putText(img, text, (60, y), font, scale, black, thick, cv2.LINE_AA)
    return img


if __name__ == "__main__":
    ok, buf = cv2.imencode(".jpg", build(), [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    OUT.write_bytes(buf.tobytes())
    print(f"escrito: {OUT}")
