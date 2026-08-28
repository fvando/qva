"""Ponto de entrada FastAPI (TASK-001).

Monta os routers e serve a interface web estática. A lógica de negócio vive
nos serviços (`app/services/`), nunca aqui.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import camera, capture, health, websocket
from app.config import get_settings
from app.dependencies import get_llm_client
from app.llm.http_client import HttpLLMClient
from app.logging_config import configure_logging

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Fecha o httpx.AsyncClient do LLM ao encerrar.
    client = get_llm_client()
    if isinstance(client, HttpLLMClient):
        await client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Question Vision Assistant", version=__version__, lifespan=lifespan
    )

    app.include_router(health.router)
    app.include_router(camera.router)
    app.include_router(capture.router)
    app.include_router(websocket.router)

    if _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")

    return app


app = create_app()
