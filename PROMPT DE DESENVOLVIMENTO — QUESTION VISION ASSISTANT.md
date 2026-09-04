# PROMPT DE DESENVOLVIMENTO — QUESTION VISION ASSISTANT

Quero que desenvolvas uma aplicação chamada **Question Vision Assistant**, em Python, com arquitetura inicialmente monolítica e execução local.

O objetivo é capturar através de uma webcam a imagem de uma tela contendo uma questão de estudo/simulado, processar essa imagem, identificar automaticamente o enunciado e as alternativas, enviar a questão para um serviço LLM já existente em Docker na rede local e disponibilizar o resultado em uma interface web responsiva acessível pelo telemóvel.

A solução deve ser simples, modular, rápida e preparada para posteriormente suportar webcam IP via Wi-Fi/RTSP.

## 1. Stack obrigatória

Backend:
- Python 3.12+
- FastAPI
- Uvicorn
- OpenCV
- Pydantic
- httpx para comunicação assíncrona com o serviço LLM
- WebSocket para atualização em tempo real
- SQLite inicialmente, apenas se necessário para histórico/configuração

Frontend:
- Preferencialmente HTML + CSS + JavaScript simples no primeiro MVP
- Não usar React inicialmente, salvo se houver benefício concreto
- Layout responsivo para telemóvel
- Comunicação com backend via REST + WebSocket

Infraestrutura:
- Aplicação executando localmente
- Serviço LLM já existente executando em outro container Docker
- Comunicação pela rede Docker ou pela LAN
- Configuração por `.env`
- Não acoplar a aplicação a um fornecedor específico de LLM

## 2. Arquitetura desejada

Implementar os seguintes módulos lógicos:

camera
image_processor
question_extractor
llm_client
question_solver
change_detector
api
websocket_manager
history
config

Fluxo principal:

Webcam
→ captura do frame
→ detecção da região da tela
→ correção de perspectiva
→ melhoria da imagem
→ detecção de mudança
→ identificação de nova questão
→ extração estruturada da questão
→ chamada ao serviço LLM
→ resposta estruturada
→ envio via WebSocket
→ apresentação no telemóvel

## 3. Captura da câmera

Criar uma abstração chamada:

CameraSource

Interface esperada:

```python
class CameraSource:
    def open(self):
        ...

    def capture(self):
        ...

    def close(self):
        ...

    def is_available(self) -> bool:
        ...
```

Implementações iniciais:

```python
USBCamera
```

Preparar arquitetura para:

```python
RTSPCamera
HTTPIPCamera
```

O sistema deve permitir configurar:

```env
CAMERA_TYPE=usb
CAMERA_DEVICE=0
```

Posteriormente:

```env
CAMERA_TYPE=rtsp
CAMERA_URL=rtsp://...
```

## 4. Preview da webcam

Criar endpoint:

```text
GET /api/camera/status
```

Resposta:

```json
{
  "available": true,
  "type": "usb",
  "device": "0"
}
```

Criar endpoint para preview:

```text
GET /api/camera/frame
```

ou streaming MJPEG:

```text
GET /api/camera/stream
```

A interface web deve permitir visualizar a câmera em tempo real para posicionamento da tela.

## 5. Captura manual

Criar endpoint:

```text
POST /api/capture
```

Fluxo:

1. Capturar frame.
2. Validar nitidez.
3. Detectar região da tela.
4. Corrigir perspectiva.
5. Recortar apenas a área útil.
6. Melhorar contraste se necessário.
7. Enviar a imagem para o pipeline de interpretação.

Resposta inicial:

```json
{
  "capture_id": "uuid",
  "status": "processing"
}
```

## 6. Processamento de imagem

Criar classe:

```python
ImageProcessor
```

Responsabilidades:

- resize
- crop
- detecção de bordas
- correção de perspectiva
- deskew
- contraste
- redução de reflexo quando possível
- avaliação de blur
- avaliação de brilho
- normalização

Criar métricas:

```text
sharpness_score
brightness_score
perspective_score
```

Se a imagem estiver ruim:

```json
{
  "status": "image_quality_error",
  "reason": "blur_detected"
}
```

## 7. Detecção automática de nova questão

Não enviar todos os frames para o LLM.

Criar:

```python
ChangeDetector
```

Utilizar técnicas leves como:

- perceptual hash
- SSIM
- diferença de histogramas
- diferença estrutural entre regiões

Fluxo:

```text
frame atual
→ comparação com frame anterior
→ mudança significativa?
    não → ignorar
    sim → aguardar estabilização
→ capturar frame definitivo
```

Adicionar configuração:

```env
AUTO_CAPTURE_ENABLED=false
CHANGE_THRESHOLD=0.25
STABILIZATION_MS=800
```

No MVP, deixar captura automática desligada por padrão.

## 8. Extração da questão

A aplicação deve suportar dois modos.

### Modo A — multimodal

Enviar diretamente a imagem para um modelo Vision.

Preferido quando o serviço LLM local suporta imagens.

### Modo B — OCR + LLM

Quando o modelo local não suporta imagens:

imagem
→ OCR
→ texto
→ LLM

Criar abstração:

```python
QuestionExtractor
```

Resultado esperado:

```json
{
  "type": "multiple_choice",
  "language": "pt",
  "question": "Qual das estruturas...",
  "options": {
    "A": "Pilha",
    "B": "Árvore binária",
    "C": "Lista duplamente encadeada",
    "D": "Fila circular"
  },
  "code": null,
  "has_image": false
}
```

Também aceitar:

```text
multiple_choice
true_false
open_question
code_question
math_question
unknown
```

## 9. Integração com meu LLM local

Não assumir Ollama diretamente.

Criar interface genérica:

```python
class LLMClient:
    async def generate(self, request):
        ...
```

Implementar primeiro:

```python
HttpLLMClient
```

Configuração:

```env
LLM_BASE_URL=http://host.docker.internal:8001
LLM_ENDPOINT=/v1/chat/completions
LLM_MODEL=my-local-model
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=30
```

Deve funcionar tanto se o backend Python estiver:

- no host
- dentro de Docker
- na mesma docker-compose network do LLM

Criar tratamento explícito para:

- timeout
- conexão recusada
- HTTP 4xx
- HTTP 5xx
- resposta inválida
- JSON malformado

## 10. Descoberta de capacidade do modelo

Criar configuração:

```env
LLM_SUPPORTS_VISION=true
```

Se true:

imagem
→ LLM multimodal

Se false:

imagem
→ OCR
→ LLM textual

O código de negócio não deve depender dessa diferença.

## 11. Prompt de extração da questão

Usar uma instrução semelhante:

Você é um extrator de questões.

Analise a imagem fornecida e identifique apenas o conteúdo acadêmico principal.

Extraia:
- enunciado
- alternativas
- código
- fórmulas
- idioma
- tipo da questão

Não resolva a questão nesta etapa.

Retorne exclusivamente JSON válido no seguinte formato:

```json
{
  "type": "",
  "language": "",
  "question": "",
  "options": {},
  "code": null,
  "has_image": false,
  "confidence": 0.0
}
```

Não adicionar markdown.

## 12. Prompt de resolução

Separar completamente extração e resolução.

Prompt:

Você é um assistente educacional para resolução de questões de estudo e simulados.

Analise cuidadosamente a questão recebida.

Para questões de múltipla escolha:
1. resolva a questão;
2. determine a alternativa mais adequada;
3. explique resumidamente o motivo;
4. estime a confiança;
5. se houver ambiguidade, indique-a claramente.

Não invente informação ausente.

Retorne exclusivamente JSON válido:

```json
{
  "answer": "D",
  "answer_text": "Fila circular",
  "explanation": "Uma fila circular...",
  "confidence": 0.94,
  "ambiguous": false
}
```

## 13. QuestionSolver

Criar:

```python
QuestionSolver
```

Responsabilidades:

- receber Question
- montar prompt
- chamar LLMClient
- validar JSON
- normalizar resposta
- tratar erro
- medir latência

Estrutura:

```python
class QuestionSolver:
    async def solve(self, question):
        ...
```

## 14. Resposta consolidada

A API deverá retornar:

```json
{
  "id": "uuid",
  "status": "completed",
  "question": {
    "type": "multiple_choice",
    "question": "...",
    "options": {
      "A": "...",
      "B": "...",
      "C": "...",
      "D": "..."
    }
  },
  "result": {
    "answer": "D",
    "answer_text": "Fila circular",
    "explanation": "...",
    "confidence": 0.94
  },
  "timing": {
    "capture_ms": 42,
    "image_processing_ms": 81,
    "question_extraction_ms": 540,
    "llm_ms": 1200,
    "total_ms": 1863
  }
}
```

## 15. WebSocket

Criar endpoint:

```text
WS /ws
```

Eventos:

```json
{
  "event": "capture_started"
}
```

```json
{
  "event": "question_detected",
  "data": {}
}
```

```json
{
  "event": "answer_ready",
  "data": {}
}
```

```json
{
  "event": "error",
  "data": {}
}
```

O telemóvel deve receber a resposta imediatamente sem polling.

## 16. Interface web

Criar uma PWA ou página responsiva.

Tela principal:

- status da câmera
- status do LLM
- status do backend
- botão "Capturar"
- preview opcional
- questão detectada
- resposta
- confiança
- explicação

Apresentação móvel:

```text
Question Vision Assistant

Status
● Camera
● LLM
● Server

Questão #12

[enunciado]

Resposta sugerida

D) Fila circular

Confiança: 94%

Explicação
...

[Capturar nova questão]
```

## 17. Estados visuais

Implementar:

```text
idle
capturing
processing_image
extracting_question
solving
completed
error
```

Nunca deixar a UI sem feedback.

## 18. Health checks

Criar:

```text
GET /health
```

Resposta:

```json
{
  "status": "healthy",
  "camera": true,
  "llm": true
}
```

Criar:

```text
GET /api/llm/status
```

para validar conexão com o serviço local.

## 19. Histórico

Opcional no primeiro MVP.

Preparar:

```text
GET /api/history
GET /api/history/{id}
DELETE /api/history/{id}
```

Guardar apenas:

- questão
- resposta
- timestamps
- métricas

Não guardar imagens por padrão.

Configuração:

```env
STORE_IMAGES=false
STORE_HISTORY=true
```

## 20. Privacidade

Adotar princípio local-first.

Por padrão:

```env
STORE_IMAGES=false
```

A imagem deve permanecer apenas em memória durante o processamento.

Não criar arquivos temporários se não for necessário.

Utilizar:

```text
OpenCV frame
→ numpy array
→ encoding JPEG em memória
→ HTTP
```

Evitar:

```text
cv2.imwrite(...)
```

## 21. Performance

Meta inicial para questões textuais simples:

```text
captura: <100 ms
processamento: <300 ms
extração: <2 s
resolução: <3 s
total: idealmente <5 s
```

Instrumentar todos os passos.

Usar:

```python
time.perf_counter()
```

Criar logging estruturado.

## 22. Concorrência

Não bloquear o event loop do FastAPI.

Operações pesadas do OpenCV devem usar:

```python
asyncio.to_thread(...)
```

Chamadas HTTP devem usar:

```python
httpx.AsyncClient
```

Não utilizar `requests` no caminho assíncrono.

## 23. Docker

Criar:

```text
Dockerfile
docker-compose.yml
.env.example
```

Se a webcam USB precisar ser acessada pelo host Windows, documentar limitações do Docker Desktop.

Permitir também executar o backend diretamente:

```text
python -m app
```

ou:

```text
uvicorn app.main:app
```

## 24. Estrutura inicial

Criar:

```text
question-vision-assistant/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── camera.py
│   │   ├── capture.py
│   │   ├── health.py
│   │   └── websocket.py
│   │
│   ├── camera/
│   │   ├── base.py
│   │   ├── usb.py
│   │   └── rtsp.py
│   │
│   ├── vision/
│   │   ├── processor.py
│   │   ├── change_detector.py
│   │   └── extractor.py
│   │
│   ├── llm/
│   │   ├── base.py
│   │   ├── http_client.py
│   │   └── solver.py
│   │
│   ├── models/
│   │   ├── question.py
│   │   └── result.py
│   │
│   ├── services/
│   │   └── pipeline.py
│   │
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── styles.css
│
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── AGENTS.md
└── README.md
```

## 25. Pipeline central

Criar:

```python
class QuestionPipeline:
    async def process_capture(self):
        ...
```

Fluxo obrigatório:

```python
frame = camera.capture()

processed = await image_processor.process(frame)

question = await question_extractor.extract(processed)

result = await solver.solve(question)

await websocket_manager.broadcast(result)

return result
```

Esse serviço deve concentrar a orquestração.

Não colocar lógica de negócio dentro dos endpoints FastAPI.

## 26. Observabilidade

Logs:

```text
CAPTURE_STARTED
CAPTURE_COMPLETED
IMAGE_PROCESSED
QUESTION_EXTRACTED
LLM_REQUEST_STARTED
LLM_REQUEST_COMPLETED
ANSWER_READY
PIPELINE_ERROR
```

Incluir:

```text
request_id
capture_id
latency_ms
model
error_type
```

Nunca logar API keys.

## 27. Testes

Criar testes unitários para:

- ImageProcessor
- ChangeDetector
- QuestionExtractor
- LLMClient
- QuestionSolver

Mockar chamadas ao LLM.

Criar imagens fixtures para testes.

Criar teste end-to-end usando imagem já armazenada, sem exigir webcam.

## 28. Modo de desenvolvimento sem câmera

Adicionar:

```env
CAMERA_TYPE=file
TEST_IMAGE=tests/fixtures/question.jpg
```

Assim posso desenvolver o pipeline sem depender fisicamente da webcam.

Criar:

```python
FileCamera
```

## 29. Segurança

A interface deve estar acessível inicialmente apenas na LAN.

Permitir bind configurável:

```env
HOST=0.0.0.0
PORT=8080
```

Preparar autenticação opcional por token.

Nunca expor o serviço diretamente para Internet no MVP.

## 30. Fase 2 — câmera IP

Depois do MVP USB, implementar suporte:

```text
RTSP
HTTP MJPEG
```

A mesma interface CameraSource deve ser mantida.

Não alterar QuestionPipeline por causa do tipo de câmera.

## 31. Critérios de aceite do MVP

O MVP será considerado concluído quando:

1. aplicação inicia sem erro;
2. webcam USB é reconhecida;
3. preview funciona;
4. botão Capturar obtém frame;
5. frame é tratado em memória;
6. questão é identificada;
7. questão é enviada ao serviço LLM local;
8. resposta retorna estruturada;
9. resposta aparece no navegador do PC;
10. resposta aparece no navegador do telemóvel;
11. WebSocket funciona;
12. imagens não são armazenadas;
13. troca futura de USB para RTSP não exige alteração do pipeline;
14. erros do LLM não derrubam a aplicação;
15. health checks funcionam.

## 32. Estratégia de implementação

Não desenvolver tudo de uma vez.

Executar na seguinte ordem:

### TASK-001
Criar estrutura do projeto e configuração.

### TASK-002
Criar USBCamera.

### TASK-003
Criar preview.

### TASK-004
Criar captura manual.

### TASK-005
Criar ImageProcessor.

### TASK-006
Criar integração HTTP com meu LLM local.

### TASK-007
Criar QuestionExtractor.

### TASK-008
Criar QuestionSolver.

### TASK-009
Criar QuestionPipeline.

### TASK-010
Criar WebSocket.

### TASK-011
Criar interface mobile.

### TASK-012
Criar FileCamera para testes.

### TASK-013
Criar métricas de latência.

### TASK-014
Criar testes.

### TASK-015
Adicionar ChangeDetector.

### TASK-016
Adicionar captura automática opcional.

### TASK-017
Adicionar RTSPCamera.

Para cada tarefa:

1. informar os arquivos criados ou alterados;
2. explicar brevemente a implementação;
3. executar testes;
4. não avançar deixando testes quebrados;
5. atualizar README;
6. manter compatibilidade com tarefas anteriores.

## Regra arquitetural principal

Preservar sempre:

```text
Camera
  ↓
ImageProcessor
  ↓
QuestionExtractor
  ↓
QuestionSolver
  ↓
LLMClient
  ↓
WebSocket/API
  ↓
Mobile UI
```

Nenhum módulo deve conhecer detalhes internos dos demais além de suas interfaces públicas.

Priorizar:
- simplicidade;
- baixa latência;
- processamento em memória;
- execução local;
- testabilidade;
- possibilidade de trocar o modelo LLM;
- possibilidade de trocar USB por câmera IP.