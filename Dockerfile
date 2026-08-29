# Question Vision Assistant — backend
FROM python:3.12-slim

# Dependências de sistema:
#  - libglib2.0-0, libgl1: OpenCV (mesmo o headless precisa)
#  - curl: healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# `pygrabber` é Windows-only (enumeração de câmeras por nome) — não instalável
# em Linux. O `list_video_input_names()` já faz fallback quando falta.
COPY requirements.txt .
RUN grep -v "pygrabber" requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

COPY app/ ./app/
COPY tests/ ./tests/

# Pré-descarrega os modelos ONNX do RapidOCR (evita o download na 1ª captura
# em modo OCR). Ignora falha — não é crítico.
RUN python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()" || true

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
