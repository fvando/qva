<#
.SYNOPSIS
  Question Vision Assistant — setup numa maquina nova (com Docker instalado).

.DESCRIPTION
  1. verifica o Docker
  2. cria/atualiza o .env (interativo)
  3. docker compose build + up -d com os perfis pedidos
  4. (opcional) puxa um modelo de visao para o Ollama local
  5. imprime os URLs de acesso

.EXAMPLE
  .\setup.ps1
  .\setup.ps1 -WithOllama -PullVision minicpm-v
  .\setup.ps1 -WithTunnel -Yes
#>

param(
  [switch]$WithOllama,
  [switch]$WithTunnel,
  [string]$PullVision = "",
  [switch]$Yes
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Say  ($m) { Write-Host $m -ForegroundColor Cyan }
function Ok   ($m) { Write-Host $m -ForegroundColor Green }
function Warn ($m) { Write-Host $m -ForegroundColor Yellow }
function Fail ($m) { Write-Host $m -ForegroundColor Red; exit 1 }

function Ask ($prompt, $default) {
  if ($Yes) { return $default }
  $suffix = if ($default) { " [$default]" } else { "" }
  $a = Read-Host "$prompt$suffix"
  if ([string]::IsNullOrWhiteSpace($a)) { return $default } else { return $a }
}

function Set-Env ($key, $val) {
  $lines = if (Test-Path .env) { Get-Content .env } else { @() }
  $found = $false
  $out = foreach ($l in $lines) {
    if ($l -match "^$([regex]::Escape($key))=") { $found = $true; "$key=$val" } else { $l }
  }
  if (-not $found) { $out += "$key=$val" }
  Set-Content .env -Value $out -Encoding UTF8
}

# --- 1. Docker -----------------------------------------------------------
Say "== 1/5  Docker =="
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail "docker nao encontrado. Instala o Docker Desktop." }
try { docker compose version | Out-Null } catch { Fail "'docker compose' indisponivel (Docker Compose v2)." }
try { docker info | Out-Null } catch { Fail "o daemon do Docker nao esta a correr." }
Ok "Docker OK"

# --- 2. .env -----------------------------------------------------------
Say "== 2/5  Configuracao (.env) =="
if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Ok "criado .env a partir do .env.example"
}

if (-not $Yes) {
  Write-Host ""
  Write-Host "Onde corre o LLM?"
  Write-Host "  1) API cloud (OpenRouter) - rapido, precisa de chave"
  Write-Host "  2) Ollama local (este script pode subir um)"
  $llm = Ask "escolhe" "1"

  if ($llm -eq "2") {
    $script:WithOllama = $true
    Set-Env LLM_MODE ocr
    Set-Env LLM_SUPPORTS_VISION false
    Set-Env LLM_BASE_URL "http://ollama:11434"
    Set-Env LLM_MODEL "qwen2.5:7b-instruct"
    Set-Env LLM_API_KEY ""
    Set-Env LLM_FALLBACK_MODELS ""
    Warn "Ollama local em modo texto (OCR). Para visao: -PullVision minicpm-v e ajusta o .env."
  } else {
    $key = Ask "chave da OpenRouter (sk-or-...)" ""
    if ($key) { Set-Env LLM_API_KEY $key }
    Set-Env LLM_MODE vision
    Set-Env LLM_SUPPORTS_VISION true
    Set-Env LLM_BASE_URL "https://openrouter.ai/api"
    Set-Env LLM_MODEL "google/gemma-4-31b-it:free"
    Set-Env LLM_FALLBACK_MODELS "minimax/minimax-m3:free,google/gemma-4-26b-a4b-it:free"
  }

  Write-Host ""
  Write-Host "Camera:"
  Write-Host "  1) browser  - o telemovel/PC que abre a UI envia os frames"
  Write-Host "  2) rtsp     - camera IP Wi-Fi (rtsp://...)"
  Write-Host "  3) file     - imagem de teste (sem camera)"
  $cam = Ask "escolhe" "1"
  switch ($cam) {
    "2" { Set-Env CAMERA_TYPE rtsp; $u = Ask "URL RTSP" ""; if ($u) { Set-Env CAMERA_URL $u } }
    "3" { Set-Env CAMERA_TYPE file }
    default { Set-Env CAMERA_TYPE browser }
  }

  $https = Ask "Servir por HTTPS? (necessario p/ a camera do browser via LAN) [s/N]" "N"
  if ($https -match "^[sSyY]") { Set-Env HTTPS true } else { Set-Env HTTPS false }

  $tun = Ask "Expor na Internet via tunel Cloudflare? [s/N]" "N"
  if ($tun -match "^[sSyY]") { $script:WithTunnel = $true }
}
Ok ".env pronto"

# --- 3. build + up -----------------------------------------------------
Say "== 3/5  Build + arranque =="
$profiles = @()
if ($WithOllama) { $profiles += @("--profile","ollama") }
if ($WithTunnel) { $profiles += @("--profile","tunnel") }

& docker compose @profiles build
& docker compose @profiles up -d
Ok "containers a correr"

# --- 4. modelo de visao (opcional) ----------------------------------
if ($WithOllama -and $PullVision) {
  Say "== 4/5  A puxar '$PullVision' para o Ollama (pode demorar) =="
  for ($i = 0; $i -lt 30; $i++) {
    try { docker compose exec -T ollama ollama list | Out-Null; break } catch { Start-Sleep 2 }
  }
  docker compose exec -T ollama ollama pull $PullVision
  Ok "modelo '$PullVision' pronto"
  Warn "Para usar visao local, no .env: LLM_SUPPORTS_VISION=true, LLM_MODE=vision,"
  Warn "LLM_MODEL=$PullVision  - depois: docker compose up -d"
} else {
  Say "== 4/5  (sem modelo de visao a puxar) =="
}

# --- 5. URLs ---------------------------------------------------------
Say "== 5/5  Acesso =="
$port = (Get-Content .env | Where-Object { $_ -match "^PORT=" }) -replace "^PORT=", ""
if (-not $port) { $port = "8080" }
$scheme = if ((Get-Content .env) -match "^HTTPS=true") { "https" } else { "http" }

Write-Host ""
Ok "  Processamento :  ${scheme}://localhost:$port/"
Ok "  Consulta      :  ${scheme}://localhost:$port/answer"

$lan = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notmatch "^127\." -and $_.PrefixOrigin -eq "Dhcp" } |
        Select-Object -First 1).IPAddress
if ($lan) { Ok "  Na LAN        :  ${scheme}://${lan}:$port/answer" }

if ($WithTunnel) {
  Write-Host ""
  Say "  Tunel Cloudflare - a obter o URL publico..."
  $url = $null
  for ($i = 0; $i -lt 20; $i++) {
    $url = (docker compose logs tunnel 2>$null | Select-String -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" |
            ForEach-Object { $_.Matches.Value } | Select-Object -Last 1)
    if ($url) { break }
    Start-Sleep 2
  }
  if ($url) { Ok "  Internet      :  $url/answer" }
  else { Warn "  URL do tunel ainda nao disponivel - ve: docker compose logs tunnel" }
}

Write-Host ""
Say "Comandos uteis:"
Write-Host "  docker compose logs -f qva        # logs do backend"
Write-Host "  docker compose ps                 # estado"
Write-Host "  docker compose down               # parar tudo"
Write-Host "  docker compose up -d              # arrancar de novo (apos editar o .env)"
