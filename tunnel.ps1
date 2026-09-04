<#
.SYNOPSIS
  Ativa / desativa um túnel Cloudflare para expor o QVA (localhost:8080) na
  Internet, sem mexer no router. Útil quando o telemóvel não chega à máquina
  pela LAN (AP isolation, redes de operadora, etc.).

.DESCRIPTION
  - Descarrega o cloudflared na primeira execução (~55 MB, guardado em ~/).
  - "start"  arranca o túnel em background e imprime o URL público.
  - "stop"   pára o túnel.
  - "status" mostra se está ativo e qual o URL.
  - "url"    imprime só o URL (para copiar).

  O URL muda a cada arranque (túnel "quick" gratuito, sem conta).

.EXAMPLE
  .\tunnel.ps1 start
  .\tunnel.ps1 status
  .\tunnel.ps1 stop
#>

param(
  [Parameter(Position = 0)]
  [ValidateSet("start", "stop", "status", "url", "restart")]
  [string]$Action = "status",

  [int]$Port = 8080
)

$ErrorActionPreference = "Stop"

$CfExe   = Join-Path $env:USERPROFILE "cloudflared.exe"
$PidFile = Join-Path $env:TEMP "qva-tunnel.pid"
$LogFile = Join-Path $env:TEMP "qva-tunnel.log"
$OutFile = Join-Path $env:TEMP "qva-tunnel-out.log"
$DownloadUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

function Ensure-Cloudflared {
  if (Test-Path $CfExe) { return }
  Write-Host "A descarregar cloudflared (~55 MB)..." -ForegroundColor Cyan
  Invoke-WebRequest -Uri $DownloadUrl -OutFile $CfExe -UseBasicParsing
  Write-Host "OK: $CfExe" -ForegroundColor Green
}

function Get-RunningPid {
  if (-not (Test-Path $PidFile)) { return $null }
  $procId = Get-Content $PidFile -ErrorAction SilentlyContinue
  if (-not $procId) { return $null }
  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if ($p -and $p.ProcessName -like "cloudflared*") { return [int]$procId }
  return $null
}

function Get-TunnelUrl {
  if (-not (Test-Path $LogFile)) { return $null }
  $txt = (Get-Content $LogFile -Raw), (Get-Content $OutFile -Raw -ErrorAction SilentlyContinue) -join "`n"
  $m = [regex]::Match($txt, "https://[a-z0-9-]+\.trycloudflare\.com")
  if ($m.Success) { return $m.Value }
  return $null
}

function Warn-IfServerDown {
  try {
    Invoke-WebRequest "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
  } catch {
    Write-Host "AVISO: o QVA nao responde em http://127.0.0.1:$Port" -ForegroundColor Yellow
    Write-Host "       arranca-o primeiro:  python -m app" -ForegroundColor Yellow
  }
}

function Start-Tunnel {
  $existing = Get-RunningPid
  if ($existing) {
    Write-Host "Tunel ja esta a correr (PID $existing)." -ForegroundColor Yellow
    Show-Status
    return
  }

  Ensure-Cloudflared
  Warn-IfServerDown

  Remove-Item $LogFile, $OutFile -ErrorAction SilentlyContinue

  $proc = Start-Process -FilePath $CfExe `
    -ArgumentList "tunnel", "--url", "http://localhost:$Port", "--no-autoupdate" `
    -RedirectStandardError $LogFile -RedirectStandardOutput $OutFile `
    -PassThru -WindowStyle Hidden

  Set-Content $PidFile $proc.Id
  Write-Host "cloudflared arrancado (PID $($proc.Id)). A aguardar o URL..." -ForegroundColor Cyan

  $url = $null
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    $url = Get-TunnelUrl
    if ($url) { break }
  }

  if (-not $url) {
    Write-Host "Nao consegui obter o URL. Log:" -ForegroundColor Red
    Get-Content $LogFile -Raw
    return
  }

  # espera o DNS propagar
  for ($i = 0; $i -lt 8; $i++) {
    try {
      Invoke-WebRequest "$url/health" -UseBasicParsing -TimeoutSec 10 | Out-Null
      break
    } catch { Start-Sleep -Seconds 5 }
  }

  Write-Host ""
  Write-Host "======================================================================" -ForegroundColor Green
  Write-Host "  TUNEL ATIVO" -ForegroundColor Green
  Write-Host ""
  Write-Host "  Processamento : $url/"
  Write-Host "  Consulta      : $url/answer"
  Write-Host ""
  Write-Host "  (na 1a visita, a Cloudflare pode pedir para clicar em continuar)"
  Write-Host "  Para desligar :  .\tunnel.ps1 stop"
  Write-Host "======================================================================" -ForegroundColor Green
}

function Stop-Tunnel {
  $procId = Get-RunningPid
  if (-not $procId) {
    # tenta apanhar qualquer cloudflared perdido
    $stray = Get-Process cloudflared -ErrorAction SilentlyContinue
    if ($stray) {
      $stray | Stop-Process -Force
      Write-Host "Terminado(s) $($stray.Count) processo(s) cloudflared." -ForegroundColor Green
    } else {
      Write-Host "Nenhum tunel a correr." -ForegroundColor Yellow
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    return
  }
  Stop-Process -Id $procId -Force
  Remove-Item $PidFile -ErrorAction SilentlyContinue
  Write-Host "Tunel desligado (PID $procId)." -ForegroundColor Green
}

function Show-Status {
  $procId = Get-RunningPid
  if (-not $procId) {
    Write-Host "Tunel: DESLIGADO" -ForegroundColor Yellow
    Write-Host "Ativar:  .\tunnel.ps1 start"
    return
  }
  $url = Get-TunnelUrl
  Write-Host "Tunel: ATIVO (PID $procId)" -ForegroundColor Green
  if ($url) {
    Write-Host "  Processamento : $url/"
    Write-Host "  Consulta      : $url/answer"
  } else {
    Write-Host "  (URL ainda nao disponivel no log)"
  }
}

switch ($Action) {
  "start"   { Start-Tunnel }
  "stop"    { Stop-Tunnel }
  "restart" { Stop-Tunnel; Start-Sleep -Seconds 1; Start-Tunnel }
  "status"  { Show-Status }
  "url"     { $u = Get-TunnelUrl; if ($u) { Write-Output $u } else { Write-Host "sem URL (tunel desligado?)" } }
}
