"""Ponto de entrada FastAPI (TASK-001).

Monta os routers e serve a interface web estática. A lógica de negócio vive
nos serviços (`app/services/`), nunca aqui.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import camera, capture, health, websocket
from app.config import get_settings
from app.logging_config import configure_logging

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Question Vision Assistant", version=__version__)

    app.include_router(health.router)
    app.include_router(camera.router)
    app.include_router(capture.router)
    app.include_router(websocket.router)

    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")

    return app


app = create_app()
