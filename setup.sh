#!/usr/bin/env bash
#
# Question Vision Assistant — setup numa máquina nova (com Docker instalado).
#
#   ./setup.sh                 # interativo: pergunta o essencial e sobe a stack
#   ./setup.sh --ollama        # inclui um Ollama local
#   ./setup.sh --tunnel        # inclui o túnel Cloudflare (URL público)
#   ./setup.sh --ollama --tunnel --pull-vision minicpm-v
#
# O que faz:
#   1. verifica o Docker
#   2. cria o .env a partir do .env.example (se não existir), pergunta os campos-chave
#   3. `docker compose build` + `up -d` com os perfis pedidos
#   4. (opcional) puxa um modelo de visão para o Ollama local
#   5. imprime os URLs de acesso

set -euo pipefail
cd "$(dirname "$0")"

WITH_OLLAMA=0
WITH_TUNNEL=0
PULL_VISION=""
NONINTERACTIVE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --ollama) WITH_OLLAMA=1 ;;
    --tunnel) WITH_TUNNEL=1 ;;
    --pull-vision) PULL_VISION="${2:-}"; shift ;;
    --yes|-y) NONINTERACTIVE=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1"; exit 1 ;;
  esac
  shift
done

say()  { printf '\033[36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
err()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }

ask() { # ask VAR "pergunta" "default"
  local var="$1" prompt="$2" def="${3:-}" ans
  if [ "$NONINTERACTIVE" = 1 ]; then printf -v "$var" '%s' "$def"; return; fi
  if [ -n "$def" ]; then read -rp "$prompt [$def]: " ans; else read -rp "$prompt: " ans; fi
  printf -v "$var" '%s' "${ans:-$def}"
}

set_env() { # set_env KEY VALUE  — escreve/atualiza no .env
  local key="$1" val="$2"
  if grep -qE "^${key}=" .env 2>/dev/null; then
    # sed portável (cria backup e apaga)
    sed -i.bak -E "s|^${key}=.*|${key}=${val}|" .env && rm -f .env.bak
  else
    printf '%s=%s\n' "$key" "$val" >> .env
  fi
}

# ---------------------------------------------------------------------------
# 1. Docker
# ---------------------------------------------------------------------------
say "== 1/5  Docker =="
command -v docker >/dev/null || { err "docker não encontrado. Instala o Docker primeiro."; exit 1; }
docker compose version >/dev/null 2>&1 || { err "'docker compose' não disponível (Docker Compose v2)."; exit 1; }
docker info >/dev/null 2>&1 || { err "o daemon do Docker não está a correr."; exit 1; }
ok "Docker OK"

# ---------------------------------------------------------------------------
# 2. .env
# ---------------------------------------------------------------------------
say "== 2/5  Configuração (.env) =="
if [ ! -f .env ]; then
  cp .env.example .env
  ok "criado .env a partir do .env.example"
fi

if [ "$NONINTERACTIVE" = 0 ]; then
  echo
  echo "Onde corre o LLM?"
  echo "  1) API cloud (OpenRouter) — rápido, precisa de chave"
  echo "  2) Ollama local (este script pode subir um)"
  ask LLM_CHOICE "escolhe" "1"

  if [ "$LLM_CHOICE" = "2" ]; then
    WITH_OLLAMA=1
    set_env LLM_MODE ocr
    set_env LLM_SUPPORTS_VISION false
    set_env LLM_BASE_URL "http://ollama:11434"
    set_env LLM_MODEL "qwen2.5:7b-instruct"
    set_env LLM_API_KEY ""
    set_env LLM_FALLBACK_MODELS ""
    warn "Ollama local em modo texto (OCR). Para visão: --pull-vision minicpm-v e ajusta o .env."
  else
    ask OR_KEY "chave da OpenRouter (sk-or-...)" ""
    [ -n "$OR_KEY" ] && set_env LLM_API_KEY "$OR_KEY"
    set_env LLM_MODE vision
    set_env LLM_SUPPORTS_VISION true
    set_env LLM_BASE_URL "https://openrouter.ai/api"
    set_env LLM_MODEL "google/gemma-4-31b-it:free"
    set_env LLM_FALLBACK_MODELS "minimax/minimax-m3:free,google/gemma-4-26b-a4b-it:free"
  fi

  echo
  echo "Câmera:"
  echo "  1) browser  — o telemóvel/PC que abre a UI envia os frames"
  echo "  2) rtsp     — câmera IP Wi-Fi (rtsp://...)"
  echo "  3) file     — imagem de teste (sem câmera)"
  ask CAM_CHOICE "escolhe" "1"
  case "$CAM_CHOICE" in
    2) ask CAM_URL "URL RTSP" ""; set_env CAMERA_TYPE rtsp; [ -n "$CAM_URL" ] && set_env CAMERA_URL "$CAM_URL" ;;
    3) set_env CAMERA_TYPE file ;;
    *) set_env CAMERA_TYPE browser ;;
  esac

  ask WANT_HTTPS "Servir por HTTPS? (necessário p/ a câmera do browser via LAN) [s/N]" "N"
  case "$WANT_HTTPS" in [sSyY]*) set_env HTTPS true ;; *) set_env HTTPS false ;; esac

  ask WANT_TUNNEL "Expor na Internet via túnel Cloudflare? [s/N]" "N"
  case "$WANT_TUNNEL" in [sSyY]*) WITH_TUNNEL=1 ;; esac
fi
ok ".env pronto"

# ---------------------------------------------------------------------------
# 3. build + up
# ---------------------------------------------------------------------------
say "== 3/5  Build + arranque =="
PROFILES=()
[ "$WITH_OLLAMA" = 1 ] && PROFILES+=(--profile ollama)
[ "$WITH_TUNNEL" = 1 ] && PROFILES+=(--profile tunnel)

docker compose "${PROFILES[@]}" build
docker compose "${PROFILES[@]}" up -d
ok "containers a correr"

# ---------------------------------------------------------------------------
# 4. modelo de visão no Ollama (opcional)
# ---------------------------------------------------------------------------
if [ "$WITH_OLLAMA" = 1 ] && [ -n "$PULL_VISION" ]; then
  say "== 4/5  A puxar '$PULL_VISION' para o Ollama (pode demorar) =="
  # espera o Ollama responder
  for _ in $(seq 1 30); do
    docker compose exec -T ollama ollama list >/dev/null 2>&1 && break
    sleep 2
  done
  docker compose exec -T ollama ollama pull "$PULL_VISION"
  ok "modelo '$PULL_VISION' pronto"
  warn "Para usar visão local, no .env: LLM_SUPPORTS_VISION=true, LLM_MODE=vision,"
  warn "LLM_MODEL=$PULL_VISION  — depois: docker compose up -d"
else
  say "== 4/5  (sem modelo de visão a puxar) =="
fi

# ---------------------------------------------------------------------------
# 5. URLs
# ---------------------------------------------------------------------------
say "== 5/5  Acesso =="
PORT="$(grep -E '^PORT=' .env | cut -d= -f2 || true)"; PORT="${PORT:-8080}"
SCHEME="http"; grep -qE '^HTTPS=true' .env && SCHEME="https"

echo
ok  "  Processamento :  $SCHEME://localhost:$PORT/"
ok  "  Consulta      :  $SCHEME://localhost:$PORT/answer"

# IP da LAN
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')" || LAN_IP=""
[ -n "$LAN_IP" ] && ok "  Na LAN        :  $SCHEME://$LAN_IP:$PORT/answer"

if [ "$WITH_TUNNEL" = 1 ]; then
  echo
  say  "  Túnel Cloudflare — a obter o URL público…"
  for _ in $(seq 1 20); do
    URL="$(docker compose logs tunnel 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)"
    [ -n "$URL" ] && break
    sleep 2
  done
  if [ -n "${URL:-}" ]; then
    ok "  Internet      :  $URL/answer"
  else
    warn "  URL do túnel ainda não disponível — vê: docker compose logs tunnel"
  fi
fi

echo
say "Comandos úteis:"
echo "  docker compose logs -f qva        # logs do backend"
echo "  docker compose ps                 # estado"
echo "  docker compose down               # parar tudo"
echo "  docker compose up -d              # arrancar de novo (após editar o .env)"
