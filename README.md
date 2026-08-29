# Question Vision Assistant (qva)

Captura por webcam a imagem de uma tela com uma questão de estudo/simulado,
identifica enunciado e alternativas, envia a um serviço LLM local (Docker) e
mostra a resposta numa interface web responsiva acessível pelo telemóvel.

Fonte de verdade da especificação:
[`PROMPT DE DESENVOLVIMENTO — QUESTION VISION ASSISTANT.md`](PROMPT%20DE%20DESENVOLVIMENTO%20%E2%80%94%20QUESTION%20VISION%20ASSISTANT.md).
Guia do agente: [`AGENTS.md`](AGENTS.md).

## Arquitetura (pipeline)

```
Camera → ImageProcessor → QuestionExtractor → QuestionSolver → LLMClient → WebSocket/API → Mobile UI
```

Nenhum módulo conhece os detalhes internos dos outros — só as interfaces
públicas. Trocar webcam USB por câmera IP (RTSP) não altera o pipeline.

### Câmeras suportadas

| Tipo | O que é |
|---|---|
| `usb` | webcam ligada ao servidor (o PC onde corre o Python) |
| `browser` | **a câmera do dispositivo que abre a página** — o telemóvel captura e envia os frames; o servidor não abre câmera nenhuma |
| `rtsp` | câmera IP por RTSP |
| `http` | câmera IP, ou telemóvel com a app "IP Webcam", por HTTP-MJPEG |
| `file` | imagem de disco (desenvolvimento) |

Trocável na interface a qualquer momento. Para usar o telemóvel como câmera,
escolhe **"Câmera deste dispositivo"** e permite o acesso — funciona sem
instalar nada, mas **exige HTTPS** (ver abaixo).

### HTTPS (para a câmera do telemóvel)

```env
HTTPS=true
```

`python -m app` gera um certificado self-signed em `certs/` (cobre `localhost`
e os IPs da LAN) e serve por `https://`. No telemóvel, aceita o aviso de
certificado uma vez. Sem HTTPS, a câmera do browser só funciona em `localhost`.

## Estrutura

```
app/
  main.py            entrypoint FastAPI (só monta routers; sem lógica de negócio)
  __main__.py        `python -m app`
  config.py          configuração via .env (Pydantic Settings)
  logging_config.py  logging estruturado em JSON
  api/               routers HTTP (health, camera, capture, websocket)
  camera/            CameraSource (base) + USBCamera, FileCamera, factory
  vision/            ImageProcessor, ChangeDetector, QuestionExtractor
  llm/               LLMClient (base) + HttpLLMClient, QuestionSolver
  models/            contratos partilhados (Question, SolveResult, ...)
  services/          QuestionPipeline (orquestração central)
  static/            index.html + app.js + styles.css
tests/
```

## Executar

Requer Python 3.12+ (o Docker usa 3.12).

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

python -m app
# ou:  uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Abrir `http://localhost:8080/`.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

**Limitação Docker Desktop / Windows:** o acesso a uma webcam USB a partir de
um container Linux não é suportado. Para o MVP com webcam USB, correr o backend
diretamente no host. O container serve o modo `CAMERA_TYPE=file` e a fase RTSP.

## Desenvolvimento sem webcam

```bash
# .env
CAMERA_TYPE=file
TEST_IMAGE=tests/fixtures/question.jpg
```

O pipeline corre igual — a `FileCamera` devolve a imagem de disco como frame.
Para regenerar a fixture: `python tests/fixtures/make_fixture.py`.

## Testes

```bash
pytest
pytest --cov=app --cov-report=term-missing   # com cobertura (~95%)
```

Todos os testes correm sem webcam e sem serviço LLM — a câmera e o LLM são
substituídos por fakes/mocks (`httpx.MockTransport`).

## Configuração

Ver [`.env.example`](.env.example). Destaques:

| Variável | Efeito |
|---|---|
| `CAMERA_TYPE` | câmera inicial: `usb` \| `browser` \| `rtsp` \| `http` \| `file` (na UI podes trocar em runtime) |
| `TEST_IMAGE` | imagem usada por `CAMERA_TYPE=file` (dev sem webcam) |
| `LLM_BASE_URL` / `LLM_ENDPOINT` / `LLM_MODEL` | serviço LLM local (agnóstico de fornecedor) |
| `LLM_SUPPORTS_VISION` | `true` = modo A (imagem→modelo Vision); `false` = modo B (RapidOCR→texto→modelo, com extração+resolução numa só chamada) |
| `AUTO_CAPTURE_ENABLED` | captura automática (desligada no MVP) |
| `STORE_IMAGES` | `false` — imagens só em memória (local-first) |
| `AUTH_TOKEN` | vazio = sem autenticação (apenas LAN) |

## Estado da implementação

| Task | Descrição | Estado |
|---|---|---|
| TASK-001 | Estrutura do projeto e configuração | ✅ concluída |
| TASK-002 | USBCamera | ✅ concluída |
| TASK-003 | Preview da webcam | ✅ concluída |
| TASK-004 | Captura manual | ✅ concluída |
| TASK-005 | ImageProcessor | ✅ concluída |
| TASK-006 | Integração HTTP com o LLM local | ✅ concluída |
| TASK-007 | QuestionExtractor | ✅ concluída |
| TASK-008 | QuestionSolver | ✅ concluída |
| TASK-009 | QuestionPipeline | ✅ concluída |
| TASK-010 | WebSocket | ✅ concluída |
| TASK-011 | Interface mobile | ✅ concluída |
| TASK-012 | FileCamera para testes | ✅ concluída |
| TASK-013 | Métricas de latência | ✅ concluída |
| TASK-014 | Testes | ✅ concluída |
| TASK-015 | ChangeDetector | ✅ concluída |
| TASK-016 | Captura automática opcional | ✅ concluída |
| TASK-017 | RTSPCamera | ✅ concluída |

**MVP completo.** Todas as 17 tasks concluídas, 140 testes.

## Validação com LLM real (Ollama)

Testado ponta a ponta (`CAMERA_TYPE=file` + fixture) contra Ollama local em CPU:

| Configuração | Latência/questão | Resultado |
|---|---|---|
| Modo A visão (`minicpm-v`, CPU) | ~2 min | correto |
| Modo B, extração+resolução separadas (`qwen2.5:7b`) | ~48 s | correto |
| **Modo B fundido (`qwen2.5:7b`)** | **~22 s** (modelo quente) | correto |

A meta de <5 s da spec pressupõe aceleração (GPU ou API cloud) — o
`HttpLLMClient` é agnóstico, basta trocar `LLM_BASE_URL`/`LLM_API_KEY`.
Em CPU, ~20 s/questão é o realista.

OCR: `rapidocr-onnxruntime` (ONNX, sem binário externo). Fallback para
`pytesseract` se instalado.
