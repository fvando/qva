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

## Testes

```bash
pytest
```

## Configuração

Ver [`.env.example`](.env.example). Destaques:

| Variável | Efeito |
|---|---|
| `CAMERA_TYPE` | `usb` \| `file` \| `rtsp` \| `http` (só `usb`/`file` no MVP) |
| `TEST_IMAGE` | imagem usada por `CAMERA_TYPE=file` (dev sem webcam) |
| `LLM_BASE_URL` / `LLM_ENDPOINT` / `LLM_MODEL` | serviço LLM local (agnóstico de fornecedor) |
| `LLM_SUPPORTS_VISION` | escolhe modo multimodal vs. OCR+LLM (interno ao extractor) |
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
| TASK-012 | FileCamera para testes | pendente |
| TASK-013 | Métricas de latência | pendente |
| TASK-014 | Testes | pendente |
| TASK-015 | ChangeDetector | pendente |
| TASK-016 | Captura automática opcional | pendente |
| TASK-017 | RTSPCamera | pendente |

Os módulos das tasks seguintes já existem como esqueletos com a interface
pública definida e `NotImplementedError` no corpo.
