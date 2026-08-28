"""TASK-006 — HttpLLMClient (sem rede real; httpx.MockTransport)."""

import httpx
import pytest

from app.config import Settings
from app.llm.base import LLMError, LLMRequest
from app.llm.http_client import HttpLLMClient


def _settings(**over) -> Settings:
    base = dict(
        _env_file=None,
        llm_base_url="http://llm.local:8001",
        llm_endpoint="/v1/chat/completions",
        llm_model="test-model",
        llm_timeout_seconds=5.0,
    )
    base.update(over)
    return Settings(**base)


def _client(handler) -> HttpLLMClient:
    transport = httpx.MockTransport(handler)
    return HttpLLMClient(_settings(), client=httpx.AsyncClient(transport=transport))


def _ok_body(text="Resposta D"):
    return {
        "model": "test-model",
        "choices": [{"message": {"role": "assistant", "content": text}}],
    }


async def test_generate_happy_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_body("Resposta D"))

    llm = _client(handler)
    out = await llm.generate(LLMRequest(prompt="Qual a resposta?"))
    assert out.text == "Resposta D"
    assert out.model == "test-model"
    assert out.latency_ms >= 0
    assert seen["url"] == "http://llm.local:8001/v1/chat/completions"
    assert seen["payload"]["model"] == "test-model"
    assert seen["payload"]["stream"] is False


async def test_vision_payload_includes_image_when_supported():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_body())

    transport = httpx.MockTransport(handler)
    llm = HttpLLMClient(
        _settings(llm_supports_vision=True),
        client=httpx.AsyncClient(transport=transport),
    )
    await llm.generate(LLMRequest(prompt="ver isto", image_b64="QUJD"))
    content = captured["payload"]["messages"][-1]["content"]
    assert isinstance(content, list)
    assert any(p["type"] == "image_url" for p in content)


async def test_timeout_maps_to_llm_error():
    def handler(request):
        raise httpx.TimeoutException("lento", request=request)

    with pytest.raises(LLMError) as e:
        await _client(handler).generate(LLMRequest(prompt="x"))
    assert e.value.kind == "timeout"


async def test_connect_error_maps_to_connection():
    def handler(request):
        raise httpx.ConnectError("recusado", request=request)

    with pytest.raises(LLMError) as e:
        await _client(handler).generate(LLMRequest(prompt="x"))
    assert e.value.kind == "connection"


async def test_http_4xx():
    with pytest.raises(LLMError) as e:
        await _client(lambda r: httpx.Response(422, text="bad")).generate(
            LLMRequest(prompt="x")
        )
    assert e.value.kind == "http_4xx"


async def test_http_5xx():
    with pytest.raises(LLMError) as e:
        await _client(lambda r: httpx.Response(503, text="down")).generate(
            LLMRequest(prompt="x")
        )
    assert e.value.kind == "http_5xx"


async def test_bad_json():
    with pytest.raises(LLMError) as e:
        await _client(lambda r: httpx.Response(200, text="not json {")).generate(
            LLMRequest(prompt="x")
        )
    assert e.value.kind == "bad_json"


async def test_invalid_response_structure():
    with pytest.raises(LLMError) as e:
        await _client(lambda r: httpx.Response(200, json={"foo": "bar"})).generate(
            LLMRequest(prompt="x")
        )
    assert e.value.kind == "invalid_response"


async def test_empty_content_is_invalid():
    body = {"choices": [{"message": {"content": "   "}}]}
    with pytest.raises(LLMError) as e:
        await _client(lambda r: httpx.Response(200, json=body)).generate(
            LLMRequest(prompt="x")
        )
    assert e.value.kind == "invalid_response"


async def test_health_true_when_reachable():
    llm = _client(lambda r: httpx.Response(200, text="ok"))
    assert await llm.health() is True


async def test_health_false_on_error():
    def handler(request):
        raise httpx.ConnectError("nope", request=request)

    assert await _client(handler).health() is False
