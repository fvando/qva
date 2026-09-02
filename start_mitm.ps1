# Script para iniciar mitmproxy em modo interceptacao da app iSwi

$PORT = 8888
$IP = "192.168.1.4"
$ADDON = "d:\ott\qva\mitm_logger.py"
$LOG_FILE = "d:\ott\qva\mitm_traffic.log"

Write-Host "=== Iniciando mitmproxy MITM proxy ===" -ForegroundColor Green
Write-Host "Porta: $PORT"
Write-Host "IP: $IP"
Write-Host "Log: $LOG_FILE"
Write-Host ""
Write-Host "*** INSTRUCOES PARA O TELEMOVEL ***" -ForegroundColor Yellow
Write-Host "1. Vai a Definicoes > Wi-Fi > (rede) > Configuracoes avancadas"
Write-Host "2. Proxy manual: $IP`:$PORT"
Write-Host "3. Carrega o certificado CA:"
Write-Host "   - Abre em navegador: http://mitm.it"
Write-Host "   - Descarrega o certificado Android"
Write-Host "   - Instala em Definicoes > Seguranca > Certificados instalados"
Write-Host "4. Abre a app iSwi e interage com a camera"
Write-Host "5. O trafego vai aparecer em TEMPO REAL abaixo:"
Write-Host ""
Write-Host "Ctrl+C para parar."
Write-Host ""

# Inicia mitmproxy via Python module
python -m mitmproxy.tools.mitmproxy --listen-host $IP --listen-port $PORT --mode regular -s "$ADDON" --set connection_strategy=eager
