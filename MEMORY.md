# qva — Memória

Este ficheiro guarda aprendizagens persistentes para futuras sessões de agente neste repositório (`d:\ott\qva` — Question Vision Assistant).

## Regras Ativas

- `AGENTS.md` e `MEMORY.md` OFICIAIS deste projeto são os que estão na raiz do repositório (`d:\ott\qva\`). Qualquer sistema de auto-memória externo ao repo NÃO é fonte de verdade aqui — só estes dois ficheiros, versionados com o código.
- A fonte de verdade da especificação é `PROMPT DE DESENVOLVIMENTO — QUESTION VISION ASSISTANT.md` na raiz. `AGENTS.md` só resume e aponta para lá.
- Ler `AGENTS.md` e este ficheiro no início de cada sessão.
- Este projeto é independente de outros repositórios do utilizador (`d:\ott\odc`, `d:\ott\back`, `d:\ott\foa`) — não misturar memória/contexto entre eles.
- Não guardar segredos, tokens, passwords, connection strings completas ou dados pessoais desnecessários.
- **NUNCA ler ficheiros `.env` (nem qualquer ficheiro conhecido por conter segredos) com `Read`, `cat`, `type` ou qualquer comando que imprima o conteúdo completo.** Para verificar se uma variável existe, usar `grep -c "^VAR=" .env`.

## Preferências do Utilizador

- As interações neste chat devem ser em português.
- Ao final de cada interação/entrega, descrever explicitamente: Objetivo, Resultados e Próximo passo.
- Todas as etapas/tasks devem ser explicadas de forma didática — o que foi construído, por que essa opção foi escolhida, e que conceito está a ser demonstrado. Não entregar apenas um resumo técnico do diff.

## Decisões Técnicas Persistentes

- 2026-08-28: **Confirmado pelo utilizador**: este repositório (`d:\ott\qva`) é o do **Question Vision Assistant**. Os ficheiros `AGENTS.md`/`MEMORY.md` que aqui estavam pertenciam ao projeto `odc` (Ottimizia Driver Intelligence) e tinham sido copiados por engano — foram substituídos por versões próprias do QVA nesta data. O prompt de desenvolvimento na raiz é a fonte de verdade.
- Ordem de implementação (prompt secção 32): TASK-001 (estrutura + config) → TASK-002 (USBCamera) → TASK-003 (preview) → TASK-004 (captura manual) → TASK-005 (ImageProcessor) → TASK-006 (HttpLLMClient) → TASK-007 (QuestionExtractor) → TASK-008 (QuestionSolver) → TASK-009 (QuestionPipeline) → TASK-010 (WebSocket) → TASK-011 (UI mobile) → TASK-012 (FileCamera para testes) → TASK-013 (métricas de latência) → TASK-014 (testes) → TASK-015 (ChangeDetector) → TASK-016 (captura automática opcional) → TASK-017 (RTSPCamera).
- 2026-08-28: **TASK-001 concluída** — estrutura completa (`app/` com `api/`, `camera/`, `vision/`, `llm/`, `models/`, `services/`, `static/`), `config.py` (Pydantic Settings, tudo via `.env`, nenhum outro módulo lê `os.environ`), `logging_config.py` (JSON estruturado), `Dockerfile`/`docker-compose.yml`/`.env.example`/`requirements.txt`/`pytest.ini`. Módulos das tasks seguintes existem como esqueletos com interface pública definida + `NotImplementedError`. App arranca (`python -m app` / `uvicorn app.main:app`), 11 testes passam (`pytest`). Endpoints base: `/health`, `/api/llm/status`, `/api/camera/status`, `/api/capture` (501), `/ws` (stub).
- **Nota de ambiente**: host tem Python 3.10 (prompt pede 3.12+; Docker usa 3.12). Testes correm no host à mesma. `Settings(_env_file=None, ...)` nos testes para não ler o `.env` real.
- 2026-08-28: **TASK-002 concluída** — `USBCamera` (OpenCV `VideoCapture`) devolve frame BGR em memória, `_WARMUP_FRAMES=3` descartadas ao abrir, `_parse_device` aceita índice (`"0"`→0) ou caminho (`/dev/video1`). `is_available()` é uma sonda barata (abre→lê→fecha se não estava aberta) usada por `/health` e `/api/camera/status`, ambos agora reais e via `asyncio.to_thread` (I/O de hardware nunca no event loop). Nova `app/dependencies.py::get_camera` (singleton `@lru_cache` — webcam é recurso exclusivo). Testes com backend `cv2.VideoCapture` falso via `monkeypatch` + `FakeCamera` em `conftest.py` com `dependency_overrides` (sem exigir webcam). 18 testes passam.
- 2026-08-28: **TASK-003 concluída** — preview. `app/vision/encoding.py::encode_jpeg` (numpy→JPEG bytes em RAM, nunca `cv2.imwrite`; normaliza `cv2.error` de frame vazio para `ValueError`). `GET /api/camera/frame` (JPEG único, 503 se câmera indisponível) e `GET /api/camera/stream` (MJPEG `multipart/x-mixed-replace`, boundary `qvaframe`, ~10 fps). **Gerador `mjpeg_frames(camera, max_frames)` extraído da rota** — infinito em produção, limitado nos testes (o `TestClient` do Starlette consome o corpo todo antes de devolver, logo um stream infinito bloqueia — testar o gerador diretamente, nunca `client.get` sobre o `/stream`). UI (`static/`) mostra snapshot + checkbox "ao vivo". 24 testes.
- Próxima task: TASK-004 (captura manual — `POST /api/capture`, resposta 202 com `capture_id`, dispara o pipeline).
