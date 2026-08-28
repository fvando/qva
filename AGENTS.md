# qva — Question Vision Assistant — Guia do Agente

## Objetivo do Projeto

**Question Vision Assistant**: aplicação Python (FastAPI), inicialmente monolítica e de execução local, que captura por webcam a imagem de uma tela contendo uma questão de estudo/simulado, processa essa imagem, identifica automaticamente o enunciado e as alternativas, envia a questão a um serviço LLM já existente em Docker na rede local, e disponibiliza a resposta numa interface web responsiva acessível pelo telemóvel.

A especificação completa (stack obrigatória, arquitetura, módulos, endpoints, prompts, critérios de aceite do MVP e ordem de implementação TASK-001..TASK-017) está em [`PROMPT DE DESENVOLVIMENTO — QUESTION VISION ASSISTANT.md`](PROMPT%20DE%20DESENVOLVIMENTO%20%E2%80%94%20QUESTION%20VISION%20ASSISTANT.md) na raiz — **esse ficheiro é a fonte de verdade do projeto e prevalece sobre este resumo em caso de conflito.**

## Contexto Obrigatório

No início de cada sessão neste repositório:

1. Ler este ficheiro.
2. Ler `MEMORY.md`.
3. Ler o prompt de desenvolvimento completo na raiz.
4. Não usar sistema de auto-memória externo ao repositório como fonte de verdade — apenas este ficheiro e `MEMORY.md`, versionados com o código.

## Como Trabalhar

- Este é um repositório **independente** de outros projetos do utilizador (ex: `d:\ott\odc`, `d:\ott\back`, `d:\ott\foa`). Não confundir contexto, convenções ou memória entre projetos. Em particular, `AGENTS.md`/`MEMORY.md` do projeto `odc` já estiveram nesta pasta por engano — não são aplicáveis aqui.
- Seguir a ordem de implementação do prompt (secção 32): TASK-001 a TASK-017, sem desenvolver tudo de uma vez. Para cada task: (1) informar ficheiros criados/alterados; (2) explicar brevemente a implementação; (3) executar testes; (4) não avançar deixando testes quebrados; (5) atualizar README; (6) manter compatibilidade com tasks anteriores.
- Manter as alterações no menor escopo que resolve a task corrente. Não fazer refactoring não relacionado, não introduzir dependências sem justificar, não mascarar testes falhados.

## Regra Arquitetural Principal (prompt, secção final)

Preservar sempre o pipeline, sem que nenhum módulo conheça detalhes internos dos demais além das suas interfaces públicas:

```
Camera → ImageProcessor → QuestionExtractor → QuestionSolver → LLMClient → WebSocket/API → Mobile UI
```

Prioridades: simplicidade, baixa latência, processamento em memória, execução local, testabilidade, possibilidade de trocar o modelo LLM, possibilidade de trocar USB por câmera IP (RTSP/HTTP MJPEG) sem alterar o `QuestionPipeline`.

## Stack e Convenções (prompt, secções 1 e 22-24)

- Backend: Python 3.12+, FastAPI, Uvicorn, OpenCV, Pydantic, `httpx` (async) para o LLM, WebSocket para tempo real, SQLite só se necessário para histórico/config.
- Frontend: HTML + CSS + JavaScript simples no primeiro MVP (sem React salvo benefício concreto), layout responsivo para telemóvel, REST + WebSocket.
- Concorrência: nunca bloquear o event loop — OpenCV pesado via `asyncio.to_thread(...)`, HTTP via `httpx.AsyncClient`, nunca `requests` no caminho assíncrono.
- Privacidade / local-first: `STORE_IMAGES=false` por omissão, imagem só em memória durante o processamento, evitar `cv2.imwrite(...)` e ficheiros temporários.
- Configuração por `.env` / `.env.example`. Não acoplar a um fornecedor específico de LLM (interface `LLMClient` genérica; primeiro `HttpLLMClient`).
- Estrutura de pastas alvo: ver secção 24 do prompt (`app/` na raiz com `api/`, `camera/`, `vision/`, `llm/`, `models/`, `services/`, `static/`; mais `tests/`, `Dockerfile`, `docker-compose.yml`, `requirements.txt`).
- Observabilidade desde o MVP: logging estruturado com `request_id`/`capture_id`/`latency_ms`/`model`/`error_type`, instrumentar todos os passos com `time.perf_counter()`, nunca logar API keys. Health checks `GET /health` e `GET /api/llm/status`.

## Memória do Agente

Usar `MEMORY.md` como caderno de aprendizagens persistentes deste projeto. Atualizar quando: o utilizador corrigir uma preferência de trabalho; uma decisão técnica recorrente for tomada; um erro recorrente for diagnosticado com prevenção reutilizável; uma regra operacional do projeto mudar.

Não colocar segredos, tokens, passwords, connection strings completas ou dados pessoais desnecessários em `MEMORY.md`. Nunca ler ficheiros `.env` com comandos que imprimam o conteúdo completo.

## Forma de Resposta

Responder em português.

Cada entrega deve incluir explicação didática (o quê, porquê, que conceito demonstra) — não apenas um resumo técnico do diff. Ao final de cada interação, descrever explicitamente: Objetivo, Resultados e Próximo passo.
