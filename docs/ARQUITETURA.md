# Arquitetura — Question Vision Assistant

Documento de referência. Parte do desenho conceptual (diagrama
"ARQUITETURA – CAPTURA, PROCESSAMENTO E ENVIO DE RESPOSTAS") e mapeia:

1. o que já está construído vs. o desenho;
2. as duas capacidades novas pedidas — **notificação push** e **câmera
   geograficamente remota** — que o desenho original não cobre.

Última atualização: 2026-08-29 (branch `dev`, 38 commits além de `main`).

---

## 1. Estado atual vs. diagrama conceptual

### Bloco 1 — Captura da tela

| Diagrama | Código | Estado |
|---|---|---|
| Webcam Wi-Fi / USB | `USBCamera` (`CAP_MSMF`/`CAP_DSHOW`), `RTSPCamera`, `HTTPIPCamera` | ✅ |
| RTSP / HTTP / Snapshot (JPEG) | `RTSPCamera` (FFMPEG), `HTTPIPCamera`, `GET /api/camera/frame` | ✅ |
| Câmera do dispositivo que abre a UI | `BrowserCamera` + `POST /api/camera/upload-frame` (`getUserMedia`) | ✅ |
| Câmera trocável em runtime | `CameraManager` + `POST /api/camera/select`, `GET /api/camera/devices` | ✅ |
| Modo de desenvolvimento sem webcam | `FileCamera` (`CAMERA_TYPE=file`) | ✅ |

### Bloco 2 — App / Servidor (backend)

| Passo do diagrama | Código | Estado |
|---|---|---|
| 2.1 Captura de frames | `QuestionPipeline.process_capture` + `ChangeDetector` (perceptual hash + histograma) | ✅ |
| 2.2 Pré-processamento da imagem | `ImageProcessor` — deteção de tela, correção de perspetiva, deskew, CLAHE, métricas `sharpness/brightness/perspective` | ✅ |
| 2.3 Extração texto/OCR | `RapidOCREngine` (ONNX, sem binário externo); fallback `TesseractOCR` | ✅ |
| 2.4 Compreensão da questão | `QuestionExtractor` — tipo, enunciado, alternativas, código, fórmulas, idioma | ✅ |
| 2.5 Envio para LLM | `HttpLLMClient` — texto (OCR) ou imagem direta (`vision`); estilo OpenAI chat completions | ✅ |
| 2.6 Geração da resposta | `QuestionSolver` (modo `ocr`/2 chamadas) ou `extract_and_solve` (combinado, 1 chamada) | ✅ |
| **Estratégia de leitura** | `LLM_MODE` = `ocr` \| `vision` \| `hybrid`; guards de alucinação; fallback entre modelos (`LLM_FALLBACK_MODELS`) | ✅ (extra ao diagrama) |
| LLM local **ou** remota | `.env` — Ollama local, OU OpenRouter/Gemini/qualquer API OpenAI-compatível | ✅ |

### Bloco 2 — Serviços internos

| Diagrama | Código | Estado | Nota |
|---|---|---|---|
| Fila de tarefas (Redis) | `fastapi.BackgroundTasks` | ⚠️ MVP | Processamento assíncrono existe; sem Redis. Suficiente porque cada captura é 1 request rápido. Migrar para Celery/RQ só se houver volume/retries pesados. |
| Cache (evitar reprocessamento) | dedup por hash SHA-256 no upload de ficheiros; `HistoryStore` | ⚠️ parcial | Não há cache de "mesma questão → mesma resposta". `ChangeDetector` já evita reprocessar frames iguais. |
| Banco de dados (histórico, logs) | `HistoryStore` — `deque(100)` em memória | ⚠️ **em memória** | Diagrama sugere PostgreSQL. Perde-se no restart. Ver §4. |
| Configurações | `Settings` (Pydantic) via `.env` | ✅ | |
| Observabilidade | logging estruturado JSON (`CAPTURE_STARTED`…`PIPELINE_ERROR`), `GET /api/metrics` (latências avg/p50/p95) | ✅ | |

### Bloco 3 — Envio e recebimento (telemóvel)

| Diagrama | Código | Estado |
|---|---|---|
| WebSocket / tempo real | `WebSocketManager` + `WS /ws` — eventos `capture_started`/`question_detected`/`answer_ready`/`error` | ✅ |
| HTTPS / JSON | `HTTPS=true` → certificado self-signed (`app/tls.py`), SAN com IPs da LAN | ✅ |
| PWA / Web App | `manifest.webmanifest` básico | ⚠️ sem service worker (não funciona offline, sem "instalar" fiável no iOS) |
| **Notificação com a app fechada** | — | ❌ **não existe** — ver §3 |

### Deploy

| Diagrama | Código | Estado |
|---|---|---|
| Docker | `Dockerfile`, `docker-compose.yml` (backend), `docker-compose.ollama-vision.yml` (2º Ollama de visão) | ✅ |
| Servidor Linux | funciona; nota: webcam USB não é acessível de dentro de container no Docker Desktop/Windows (documentado) | ✅ |
| Rede local ou Internet | LAN ✅; Internet exige HTTPS + `AUTH_TOKEN` (este último **ainda não verificado por nenhum endpoint** — pendência) | ⚠️ |

### Resumo

**~85% alinhado com o diagrama.** As lacunas conscientes (BD em memória, fila
= BackgroundTasks) seguem o princípio "não introduzir infraestrutura
desnecessária no MVP". As duas capacidades novas (§3 e §5) estão **fora** do
diagrama original.

---

## 2. Fluxo atual (implementado)

```
┌─────────────┐   captura     ┌──────────────────────────────────────┐   WS/HTTPS   ┌───────────┐
│ Câmera      │──────────────▶│ QVA (servidor)                       │────────────▶│ Browser   │
│ USB/IP/     │  (LAN ou      │  pipeline:                           │  answer_    │ (PC ou    │
│ browser     │   upload)     │   ImageProcessor → Extractor →       │  ready      │  telemóvel│
└─────────────┘               │   [OCR|Vision] → Solver → LLM        │             │  ABERTO)  │
                              │  HistoryStore (memória) · Metrics    │             └───────────┘
                              │  LLM: Ollama local OU OpenRouter     │
                              └──────────────────────────────────────┘
```

**Limitação central:** o telemóvel só recebe a resposta **enquanto a página
está aberta** (WebSocket). E a câmera tem de estar **alcançável pelo servidor**
(mesma LAN, ou o browser/agente faz push).

---

## 3. Capacidade nova A — Notificação para telemóvel registado

### Objetivo

Enviar a resposta a um ou mais telemóveis **registados**, mesmo com a app
fechada. É *push* real, não *live update*.

### Desenho

Interface abstrata `Notifier` (mesmo padrão de `LLMClient` / `CameraSource`):

```python
class Notifier(ABC):
    async def send(self, response: ConsolidatedResponse) -> None: ...
```

Implementações: `TelegramNotifier`, `WhatsAppNotifier`, `WebPushNotifier`,
`SmsNotifier`, `NoopNotifier` (default). O `QuestionPipeline` chama
`notifier.send(response)` logo após emitir `answer_ready`. Trocar de canal =
mudar o `.env`. Falha do notifier **nunca** derruba o pipeline (mesmo
princípio já aplicado ao LLM e à câmera).

```env
NOTIFY_CHANNEL=telegram        # telegram | whatsapp | webpush | sms | none
NOTIFY_ON=completed            # completed | completed,error
```

### Comparação de canais

| Canal | Custo | Esforço | App de terceiros? | Imagem/formatação | Burocracia |
|---|---|---|---|---|---|
| **Telegram Bot** | grátis | baixo (~30 min) | sim (Telegram) | sim | nenhuma — só `/start` no bot |
| **WhatsApp** (Twilio ou Cloud API) | ~$0.005/msg (Twilio); grátis até 1000/mês (Cloud API) | médio | não | sim | **templates aprovados pela Meta (1–2 dias)** para mensagens iniciadas pelo negócio |
| **Web Push** (VAPID) | grátis | médio | não | limitada | permissão do browser; iOS só via "adicionar ao ecrã principal" |
| **SMS** (Twilio/Vonage) | ~€0.05/SMS | baixo | não | não (160 chars) | número remetente |
| **Email** (SMTP/Resend) | ~grátis | baixo | não | sim | nenhuma |

### Recomendação

**Telegram Bot** para a primeira versão: grátis, rápido, suporta a imagem da
questão + resposta formatada. Config:

```env
NOTIFY_CHANNEL=telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_IDS=111111111,222222222   # telemóveis registados
```

Registo de um telemóvel: o utilizador abre o bot, faz `/start`; um endpoint
`GET /api/notify/telegram/updates` (ou um comando no próprio bot) mostra o
`chat_id` a adicionar ao `.env`. Numa versão futura, registo self-service com
persistência em BD.

**WhatsApp** fica para quando for requisito de negócio — mesma interface
`Notifier`, só muda a implementação e a config; contar com a aprovação de
templates.

### Trabalho estimado

- `Notifier` + `TelegramNotifier` + ligação ao pipeline + `.env` + testes
  (mock da API do Telegram): **~meio dia**.
- `WhatsAppNotifier` (Twilio): **~meio dia** + tempo de aprovação Meta.

---

## 4. Persistência (BD do diagrama)

Hoje: `HistoryStore` em memória (`deque(100)`), perde-se no restart.

O diagrama pede **PostgreSQL** para histórico e logs. Quando fizer sentido:

| Opção | Quando |
|---|---|
| Manter em memória | uso pessoal, não importa perder ao reiniciar |
| **SQLite** (`aiosqlite`) | histórico tem de sobreviver a restart, um só processo, sem infra extra — **recomendado como próximo passo** |
| PostgreSQL | multi-utilizador, vários processos, relatórios, retenção longa |

A interface `HistoryStore` já isola isto — trocar o backend não toca no
pipeline. Migração para SQLite: **~2-3 h** (schema `question/result/timing/
created_at`, sem imagens; endpoints `/api/history` já existem).

---

## 5. Capacidade nova B — Câmera geograficamente remota

### ⚠️ Pré-requisito: a câmera TEM de expor RTSP ou ONVIF

A câmera candidata (mini câmera Wi-Fi "NexusGuard", Amazon `B0H3HPFCVR`) é uma
câmera OEM genérica que provavelmente só funciona com a **app do fabricante**
e roteia o vídeo pela nuvem dele. Se for esse o caso, **o QVA não consegue
ligar-se a ela** — nem localmente nem remotamente — porque não há RTSP/ONVIF
nem API aberta.

**Ação antes de qualquer implementação:** confirmar com uma app ONVIF
(Onvier, tinyCam Monitor) que a câmera expõe um URL RTSP na LAN. Se sim,
anotar o URL (`rtsp://ip:554/...`) e usar `CAMERA_TYPE=rtsp` — funciona sem
código novo. Se não, **trocar de câmera** por um modelo com RTSP/ONVIF
documentado (ex: TP-Link Tapo C100/C110 ~€20, Reolink E1).

O resto desta secção assume uma câmera com RTSP/ONVIF.

### Objetivo

A câmera está num local (ex: país A); o QVA corre noutro (ex: país B). O QVA
tem de obter frames dessa câmera e processá-los.

### Por que o desenho atual não resolve

O diagrama assume **"Webcam Wi-Fi → RTSP/HTTP → App"** na mesma rede
("Funciona em rede local (recomendado)"). Pela Internet de longa distância:

- **CGNAT** — a maioria das ligações domésticas não tem IP público; não há
  port-forward possível.
- **Segurança** — expor RTSP à Internet é um risco conhecido (scan constante
  de câmeras IP).
- **Latência / cortes** — RTSP não foi desenhado para WAN de longa distância.

### Opção B1 — Agente leve no local da câmera *(recomendada)*

Um pequeno programa (`qva-agent.py`, ~60 linhas) corre junto da câmera
(Raspberry Pi, mini-PC, ou o PC de lá). Ele:

1. lê a webcam **localmente** (USB, ou IP na LAN dele);
2. opcionalmente corre o `ChangeDetector` local — só age quando há questão nova;
3. captura um frame e faz **`POST https://<qva>/api/camera/upload-frame`**
   (a mesma rota que a `BrowserCamera` já usa), com um `AGENT_TOKEN`.

```
   [País A]                              [País B]
   webcam ──▶ qva-agent ──HTTPS POST──▶ QVA ──▶ pipeline ──▶ Notifier ──▶ telemóvel
              (saída, atravessa                 (LLM cloud)
               CGNAT/NAT sem
               configurar rede)
```

**Prós:** não exige configurar rede no lado da câmera (ligação de **saída**);
nada exposto à Internet nesse lado; barato (sem TURN, sem serviço de nuvem);
reutiliza ~90% do que já existe (`BrowserCamera` → renomear/estender para
`RemoteCamera`; `upload-frame` já feito). Escala: N agentes → 1 servidor.

**Contras:** precisa de um dispositivo sempre ligado junto da câmera; o agente
é mais um artefacto a distribuir e manter.

**Trabalho:** `qva-agent.py` (captura + retry + backoff + auth) + `AGENT_TOKEN`
no `upload-frame` + modo "pull" (agente pergunta "há pedido?") ou "push
contínuo" (agente envia a cada N s / em mudança): **~1 dia**.

### Opção B2 — Câmera IP + túnel (Tailscale / WireGuard)

A câmera fica numa LAN com um nó Tailscale (ou o router com WireGuard). O QVA
entra nessa rede virtual e liga-se à câmera por `rtsp://100.x.x.x:554/...`
(IP Tailscale). A `RTSPCamera` **já suporta isto sem alterações**.

**Prós:** zero código novo; Tailscale atravessa CGNAT; cifrado; a câmera não
fica exposta à Internet pública (só à *tailnet*).

**Contras:** é preciso instalar Tailscale nos dois lados (ou um router
compatível); depende de a câmera aceitar RTSP; ainda há latência de WAN para o
stream (mas para um snapshot pontual é aceitável).

**Trabalho:** só documentação + testar. **~2 h.**

### Opção B3 — WebRTC P2P

Agente e QVA estabelecem uma sessão WebRTC (signaling via o próprio QVA;
STUN público; TURN próprio para casos sem NAT traversal). Vídeo ao vivo de
baixa latência, robusto a NAT.

**Prós:** preview remoto **ao vivo**; melhor travessia de NAT.

**Contras:** complexidade alta (signaling, ICE, um servidor TURN — `coturn` —
com custo de banda quando o P2P falha); *overkill* se só se precisa de fotos
pontuais.

**Trabalho:** **~3-5 dias** + operar o TURN.

### Opção B4 — Serviço de câmera na nuvem (fabricante)

Câmeras Reolink/Hikvision/etc. com nuvem própria, ou `frigate` + MQTT a
publicar snapshots. O QVA lê da nuvem/broker.

**Contras:** dependência do fabricante ou de infra a montar; menos controlo.

### Comparação

| | Código novo | Rede no lado da câmera | Segurança | Latência | Custo | Complexidade |
|---|---|---|---|---|---|---|
| **B1 Agente** | ~1 dia | **nenhuma** (só saída) | alta | boa (snapshot) | ~0 | baixa |
| B2 Tailscale | ~0 (doc) | instalar Tailscale | alta | média (stream WAN) | ~0 | baixa |
| B3 WebRTC | 3-5 dias | nenhuma | alta | **ótima (ao vivo)** | TURN | alta |
| B4 Nuvem fabricante | variável | config da câmera | variável | variável | variável | média |

### Recomendação

**B1 (agente leve)** como caminho principal — resolve o cenário sem configurar
rede, é seguro e barato, e reaproveita o que já temos. **B2 (Tailscale)** como
alternativa imediata de "zero código" se o operador da câmera aceitar instalar
o Tailscale e a câmera falar RTSP.

---

## 6. Arquitetura-alvo (com as duas capacidades)

```
┌──────────────────────────┐                      ┌───────────────────────────────────────┐
│ LOCAL DA CÂMERA (país A)  │                      │ SERVIDOR QVA (país B, Docker)          │
│                          │                      │                                       │
│  webcam USB/IP           │   HTTPS POST frame   │  /api/camera/upload-frame              │
│    │                     │  (ligação de saída,  │    │                                  │
│    ▼                     │   AGENT_TOKEN)       │    ▼                                  │
│  qva-agent  ─────────────┼─────────────────────▶│  QuestionPipeline                     │
│  (ChangeDetector local,  │                      │   ImageProcessor → Extractor →        │
│   retry/backoff)         │                      │   [OCR | Vision] → Solver             │
└──────────────────────────┘                      │    │                                  │
                                                  │    ├── LLM (Ollama local | OpenRouter)│
   ┌──────────────────────┐                       │    │                                  │
   │ TELEMÓVEL REGISTADO   │◀───── Notifier ──────┤    ├── HistoryStore (SQLite)          │
   │ (app fechada)         │  Telegram/WhatsApp   │    └── Metrics / logs                 │
   └──────────────────────┘                       │                                       │
   ┌──────────────────────┐   WebSocket / HTTPS   │                                       │
   │ BROWSER (app aberta)  │◀─────────────────────┤  WS /ws  (answer_ready, ...)          │
   └──────────────────────┘                       └───────────────────────────────────────┘
```

---

## 7. Backlog priorizado

| # | Item | Depende de | Esforço | Valor |
|---|---|---|---|---|
| 1 | **Autenticação por token** (`AUTH_TOKEN` verificado nos endpoints + WS) | — | ~3 h | pré-requisito para expor à Internet |
| 2 | **`Notifier` + `TelegramNotifier`** | 1 | ~meio dia | resposta chega com a app fechada |
| 3 | **`qva-agent.py`** (câmera remota, opção B1) | 1 | ~1 dia | câmera noutro local/país |
| 4 | **Persistência SQLite** (`HistoryStore`) | — | ~2-3 h | histórico sobrevive a restart |
| 5 | Documentar/testar **Tailscale + RTSPCamera** (opção B2) | — | ~2 h | alternativa "zero código" para câmera remota |
| 6 | **PWA completa** (service worker, ícones, offline shell) | — | ~meio dia | "instalar" no telemóvel, arranque rápido |
| 7 | `WhatsAppNotifier` (Twilio) | 2 | ~meio dia + aprovação Meta | canal preferido do utilizador final |
| 8 | Cache "questão → resposta" (hash do texto extraído) | 4 | ~3 h | não repagar o LLM por questões repetidas |

**Ordem sugerida:** 1 → 2 → 4 → 3 → 5 → 6 → 7 → 8.
Justificação: a auth (1) desbloqueia tudo o que envolve Internet; a
notificação (2) é o maior salto de valor percebido; a persistência (4) é
barata e evita perder histórico; o agente (3) resolve o cenário remoto.
