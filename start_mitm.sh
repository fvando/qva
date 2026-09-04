#!/bin/bash

# Script para iniciar mitmproxy em modo interceptação da app iSwi
# Usa o addon mitm_logger.py para logar tráfego

PORT=8888
CERT_DIR="$HOME/.mitmproxy"

echo "=== Iniciando mitmproxy MITM proxy ==="
echo "Porta: $PORT"
echo "Log: d:/ott/qva/mitm_traffic.log"
echo ""
echo "*** INSTRUÇÕES PARA O TELEMÓVEL ***"
echo "1. Vai a Definições > Wi-Fi > (rede) > Configurações avançadas"
echo "2. Proxy manual: 192.168.1.4:$PORT"
echo "3. Carrega o certificado CA:"
echo "   - Abre em navegador: http://mitm.it"
echo "   - Descarrega o certificado Android"
echo "   - Instala em Definições > Segurança > Certificados instalados"
echo "4. Abre a app iSwi e interage com a câmera"
echo "5. O tráfego vai aparecer em TEMPO REAL abaixo:"
echo ""
echo "Ctrl+C para parar."
echo ""

mitmproxy \
  --listen-host 192.168.1.4 \
  --listen-port $PORT \
  --mode regular \
  -s "d:/ott/qva/mitm_logger.py" \
  --set connection_strategy=eager
