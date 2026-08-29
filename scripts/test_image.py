"""Testa o pipeline completo com uma imagem tua (sem webcam, sem servidor).

    python scripts/test_image.py caminho/para/foto.jpg

Usa a configuração do `.env`. Mostra: métricas de qualidade da imagem, questão
extraída, resposta e latências de cada passo.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import dependencies as d  # noqa: E402
from app.services.pipeline import QuestionPipeline  # noqa: E402
from app.vision.processor import ImageProcessor, ImageQualityError  # noqa: E402


def _load(path: str):
    import numpy as np

    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"não é uma imagem válida: {path}")
    return img


async def main(path: str) -> None:
    for f in (
        d.get_camera_manager, d.get_llm_client, d.get_capture_registry,
        d.get_image_processor, d.get_metrics, d.get_history,
        d.get_websocket_manager, d.get_change_detector,
    ):
        f.cache_clear()

    frame = _load(path)
    print(f"imagem: {path}  {frame.shape[1]}x{frame.shape[0]}")

    # 1. Qualidade da imagem (isolado, para diagnóstico) -----------------
    try:
        processed = ImageProcessor().process_sync(frame)
        print("  métricas:", processed.metrics(), "| tela detetada:", processed.screen_detected)
    except ImageQualityError as e:
        print(f"  IMAGEM REJEITADA: {e.reason}")
        print("  (ajusta a iluminação/foco, ou baixa MIN_SHARPNESS/brilho em app/vision/processor.py)")
        return

    # 2. Pipeline completo (com o frame já carregado) -------------------
    reg = d.get_capture_registry()
    pipe = d.build_pipeline()  # mesma configuração do servidor (inclui vision_llm)

    t0 = time.time()
    job = reg.create()
    resp = await pipe.process_capture(job.id, frame=frame)
    wall = time.time() - t0

    print()
    print("STATUS:", resp.status)
    if resp.error:
        print("ERRO:", resp.error)
    if resp.question:
        print("TIPO:", resp.question.type.value, "| idioma:", resp.question.language)
        print("ENUNCIADO:", resp.question.question)
        for k, v in resp.question.options.items():
            print(f"   {k}) {v}")
        if resp.question.code:
            print("CÓDIGO:\n", resp.question.code)
    if resp.result:
        print()
        print(f"RESPOSTA: {resp.result.answer}) {resp.result.answer_text}")
        print(f"CONFIANÇA: {resp.result.confidence:.0%}")
        if resp.result.ambiguous:
            print("AMBÍGUA: sim")
        print("EXPLICAÇÃO:", resp.result.explanation)
    t = resp.timing
    print()
    print(f"TIMING: imagem={t.image_processing_ms:.0f}ms "
          f"extração={t.question_extraction_ms:.0f}ms "
          f"resolução={t.llm_ms:.0f}ms total={t.total_ms:.0f}ms (wall {wall:.1f}s)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("uso: python scripts/test_image.py caminho/para/foto.jpg")
    asyncio.run(main(sys.argv[1]))
