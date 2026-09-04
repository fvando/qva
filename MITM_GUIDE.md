# Interceptação MITM da App iSwi — Guia Completo

## Objetivo
Capturar todo o tráfego HTTP/HTTPS da app iSwi no telemóvel para descobrir:
- URLs de streaming
- Endpoints de API local
- Protocolo de comunicação câmera-cloud

## Pré-requisitos
- ✅ mitmproxy instalado (`pip install mitmproxy`)
- ✅ Telemóvel Android na mesma rede Wi-Fi que o portátil
- ✅ App iSwi instalada e a funcionar no telemóvel

## Passo 1: Iniciar mitmproxy no portátil

**Windows PowerShell:**
```powershell
cd d:\ott\qva
.\start_mitm.ps1
```

**Bash/Linux:**
```bash
cd d/ott/qva
bash start_mitm.sh
```

Vai ver algo como:
```
=== Iniciando mitmproxy MITM proxy ===
Porta: 8888
IP: 192.168.1.4
Log: d:/ott/qva/mitm_traffic.log
```

**Deixa o terminal aberto!**

---

## Passo 2: Configurar o telemóvel Android

1. **Vai a Definições > Wi-Fi**
2. **Clica na rede que estás ligado (mesma que o portátil)**
3. **"Editar" / "Modificar" / "Avançado"**
4. **Procura "Proxy" ou "Configuração de proxy":**
   - Muda para **"Proxy manual"**
   - **Hostname/Servidor:** `192.168.1.4`
   - **Porta:** `8888`
5. **Guarda**

---

## Passo 3: Instalar certificado CA no telemóvel

O telemóvel vai dar erro de "certificado não confiável" da app iSwi. Precisas instalar o certificado CA do mitmproxy.

1. **Abre o navegador no telemóvel**
2. **Vai a:** `http://mitm.it`
3. **Vais ver página do mitmproxy com 4 links de download**
4. **Descarrega "Android Certificate"** (arquivo `.cer` ou `.pem`)
5. **Vai a Definições > Segurança > Certificados instalados > Instalar**
6. **Escolhe o ficheiro descarregado**
7. **Nome:** deixa por defeito ou "mitmproxy"
8. **Guarda**

---

## Passo 4: Usar a app iSwi no telemóvel

1. **Abre a app iSwi**
2. **Usa-a normalmente:**
   - Vê a câmera ao vivo
   - Interage com as definições
   - Faz o que fazias antes
3. **Tudo será interceptado pelo portátil**

---

## Passo 5: Analisar o log

Enquanto usas a app, vais ver tráfego em TEMPO REAL no terminal do mitmproxy:

```
REQUEST: GET iswi.example.com/api/device/192.168.1.23/stream
  Headers: {...}
  Body: {...}

RESPONSE: 200 from iswi.example.com/api/device/192.168.1.23/stream
  Headers: {...}
  Body: {...}
```

**Guarda o terminal aberto e procura por:**
- URLs com "stream", "rtsp", "video"
- Endpoints com "device", "camera", "ip"
- Respostas com URLs ou tokens

O log completo também fica em: **`d:/ott/qva/mitm_traffic.log`**

---

## Passo 6: Parar e limpar

1. **Ctrl+C no terminal do mitmproxy** para parar
2. **No telemóvel, volta Proxy para "Nenhum"** em Definições > Wi-Fi
3. **Opcional:** remove o certificado em Definições > Segurança > Certificados instalados

---

## O que procurar no tráfego

### URLs interessantes
```
rtsp://
/stream
/video
/api/device
/api/camera
/gateway
```

### Respostas interessantes
```json
{
  "stream_url": "rtsp://...",
  "gateway": "...",
  "server": "...",
  "endpoint": "..."
}
```

---

## Troubleshooting

### "Certificado não confiável" na app
→ Instalaste o certificado CA no telemóvel? (passo 3)

### Sem tráfego a aparecer
→ A app pode estar a usar pinning de certificado (bloqueia proxies)
→ Ou o proxy não está ligado (verifica passo 1)

### "Connection refused" no telemóvel
→ Verifica se o portátil IP é `192.168.1.4` (passo 2)
→ Verifica se ambos estão no Wi-Fi `192.168.1.x`

---

## Resultado esperado

Se tudo correr bem, vais ver endpoints como:

```
REQUEST: POST iswi-api.example.com/v1/device/stream
  Body: {"device_id": "192.168.1.23", "auth_token": "xxx"}

RESPONSE: 200
  Body: {"rtsp_url": "rtsp://192.168.1.23:554/stream1", "user": "admin", "pass": "xxx"}
```

Ou algo semelhante — qualquer URL local que revele como contactar a câmera.
