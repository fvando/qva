"""Seletor de modelo LLM — /api/llm/models e /api/llm/select."""

import httpx
import pytest

from app.config import Settings
from app.llm.http_client import HttpLLMClient


def _client_with_tags(models):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": m} for m in models]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    transport = httpx.MockTransport(handler)
    s = Settings(_env_file=None, llm_base_url="http://llm.local:11434", llm_model="a")
    return HttpLLMClient(s, client=httpx.AsyncClient(transport=transport))


async def test_list_models_from_tags():
    llm = _client_with_tags(["qwen2.5:7b", "llama3.2:3b"])
    assert await llm.list_models() == ["llama3.2:3b", "qwen2.5:7b"]


async def test_list_models_empty_when_no_tags_route():
    def handler(request):
        return httpx.Response(404)

    llm = HttpLLMClient(
        Settings(_env_file=None),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert await llm.list_models() == []


def test_set_model_changes_active():
    llm = HttpLLMClient(Settings(_env_file=None, llm_model="a"))
    assert llm.model == "a"
    llm.set_model("b")
    assert llm.model == "b"


# -- endpoints (via FakeLLM do conftest) ------------------------------
def test_models_endpoint_returns_active(client):
    r = client.get("/api/llm/models")
    assert r.status_code == 200
    body = r.json()
    assert "active" in body and "models" in body
    assert body["active"] in body["models"]


def test_select_endpoint_rejects_non_http_client(client):
    # o conftest injeta FakeLLM, que não é HttpLLMClient
    r = client.post("/api/llm/select", json={"model": "x"})
    assert r.status_code == 400


def test_select_endpoint_with_real_http_client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.dependencies import get_llm_client
    from app.main import create_app
    from tests.conftest import FakeCameraManager, TEST_SETTINGS
    from app.config import get_settings
    from app.dependencies import get_camera, get_camera_manager

    llm = _client_with_tags(["qwen2.5:7b", "llama3.2:3b"])
    cam = FakeCameraManager()
    app = create_app()
    app.dependency_overrides[get_llm_client] = lambda: llm
    app.dependency_overrides[get_camera] = lambda: cam
    app.dependency_overrides[get_camera_manager] = lambda: cam
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    c = TestClient(app)

    assert c.post("/api/llm/select", json={"model": "llama3.2:3b"}).status_code == 200
    assert llm.model == "llama3.2:3b"
    assert c.get("/api/llm/status").json()["model"] == "llama3.2:3b"


def test_allowlist_parsing():
    from app.api.health import _allowed_models

    assert _allowed_models(Settings(_env_file=None, llm_models_allowed="")) is None
    assert _allowed_models(
        Settings(_env_file=None, llm_models_allowed="a, b ,c")
    ) == {"a", "b", "c"}
