"""`HttpLLMClient` — fala com o serviço LLM local via HTTP (TASK-006).

Assume um endpoint compatível com a API de *chat completions* da OpenAI
(o formato mais comum entre servidores locais: Ollama com `/v1`, LM Studio,
llama.cpp server, vLLM, ...), mas **não** assume nenhum fornecedor: o URL, o
caminho, o modelo e a chave vêm todos da configuração.

Tratamento de erro explícito (secção 9 do prompt), cada caso → `LLMError(kind)`:
  timeout | connection | http_4xx | http_5xx | invalid_response | bad_json
"""

from __future__ import annotations

import logging
import time

import httpx

from app.config import Settings
from app.llm.base import LLMClient, LLMError, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class HttpLLMClient(LLMClient):
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        # Modelo ativo — começa no do `.env`, pode ser trocado na UI em runtime.
        self._model = settings.llm_model
        # Permite injetar um cliente nos testes (httpx.MockTransport).
        self._client = client
        self._owns_client = client is None

    @property
    def model(self) -> str:
        return self._model

    def set_model(self, model: str) -> None:
        self._model = model

    async def list_models(self) -> list[str]:
        """Modelos disponíveis no serviço.

        Tenta `/api/tags` (Ollama) e depois `/v1/models` (OpenAI/OpenRouter/...).
        Devolve `[]` se nenhuma rota responder."""
        base = self._settings.llm_base_url.rstrip("/")
        headers = self._headers()

        # Ollama
        try:
            resp = await self._get_client().get(f"{base}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                names = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                if names:
                    return sorted(names)
        except (httpx.HTTPError, ValueError):
            pass

        # OpenAI-style
        for path in ("/v1/models", "/models"):
            try:
                resp = await self._get_client().get(
                    f"{base}{path}", headers=headers, timeout=8.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", data if isinstance(data, list) else [])
                    names = [x.get("id", "") for x in items if isinstance(x, dict) and x.get("id")]
                    if names:
                        return sorted(names)
            except (httpx.HTTPError, ValueError):
                continue
        return []

    # -- ciclo de vida do cliente httpx -----------------------------------
    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # -- construção do payload -----------------------------------------
    def _build_messages(self, request: LLMRequest) -> list[dict]:
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "user", "content": request.system})

        if request.image_b64 and self._settings.llm_supports_vision:
            # Formato multimodal estilo OpenAI: lista de partes texto+imagem.
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{request.image_b64}"
                            },
                        },
                    ],
                }
            )
        else:
            messages.append({"role": "user", "content": request.prompt})
        return messages

    def _build_payload(self, request: LLMRequest) -> dict:
        return {
            "model": self._model,
            "messages": self._build_messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key}"
        return headers

    # -- extração da resposta -----------------------------------------
    @staticmethod
    def _extract_text(data: dict) -> str:
        """Tira o texto de uma resposta estilo OpenAI chat completions."""
        try:
            choices = data["choices"]
            message = choices[0]["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("invalid_response", f"estrutura inesperada: {exc}") from exc

        if isinstance(content, list):  # resposta multimodal
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise LLMError("invalid_response", "conteúdo vazio ou não textual")
        return content

    # -- chamada principal ------------------------------------------------
    async def generate(self, request: LLMRequest) -> LLMResponse:
        url = self._settings.llm_url
        payload = self._build_payload(request)
        t0 = time.perf_counter()

        logger.info(
            "LLM_REQUEST_STARTED", extra={"model": self._model}
        )
        try:
            resp = await self._get_client().post(
                url, json=payload, headers=self._headers()
            )
        except httpx.TimeoutException as exc:
            raise LLMError("timeout", f"sem resposta em {self._settings.llm_timeout_seconds}s") from exc
        except httpx.ConnectError as exc:
            raise LLMError("connection", f"ligação recusada a {url}") from exc
        except httpx.HTTPError as exc:
            raise LLMError("connection", f"erro de transporte: {exc}") from exc

        if 400 <= resp.status_code < 500:
            raise LLMError("http_4xx", f"{resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 500:
            raise LLMError("http_5xx", f"{resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMError("bad_json", f"corpo não é JSON: {resp.text[:200]}") from exc

        if not isinstance(data, dict):
            raise LLMError("invalid_response", "JSON de topo não é um objeto")

        text = self._extract_text(data)
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "LLM_REQUEST_COMPLETED",
            extra={"model": self._model, "latency_ms": round(latency_ms, 1)},
        )
        return LLMResponse(
            text=text,
            model=data.get("model", self._model),
            latency_ms=latency_ms,
            raw=data,
        )

    async def health(self) -> bool:
        """Sonda barata: verifica que o serviço está acessível (sem gastar
        uma inferência). Para APIs cloud, um GET a `/v1/models` ou ao host.
        Qualquer resposta HTTP (mesmo 401/404) significa "acessível"."""
        base = self._settings.llm_base_url.rstrip("/")
        headers = self._headers()
        for url in (f"{base}/v1/models", f"{base}/api/tags", base):
            try:
                resp = await self._get_client().get(url, headers=headers, timeout=4.0)
                # 2xx/3xx/4xx = o serviço respondeu; só 5xx / erro de rede = down
                if resp.status_code < 500:
                    return True
            except httpx.HTTPError:
                continue
        return False
