# Testar o QVA com fotos reais de questões

O pipeline foi validado com uma imagem sintética. Para o afinar ao teu uso real
(webcam a apontar a um ecrã), precisas de fotos verdadeiras.

## Preparação (uma vez)

```bash
cp .env.example .env
```

Edita o `.env`:

```env
# Ollama de texto que já tens (modo B, OCR + LLM):
LLM_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b-instruct
LLM_SUPPORTS_VISION=false

# OU o Ollama de visão isolado (modo A, imagem direta):
#   docker compose -f docker-compose.ollama-vision.yml up -d
#   docker exec -it qva-ollama-vision ollama pull minicpm-v
# LLM_BASE_URL=http://localhost:11435
# LLM_MODEL=minicpm-v
# LLM_SUPPORTS_VISION=true
```

## Testar uma imagem (sem webcam, sem servidor)

Tira uma foto de uma questão (telemóvel, screenshot, webcam) e:

```bash
python scripts/test_image.py caminho/para/foto.jpg
```

Mostra: métricas de qualidade da imagem, questão extraída, resposta,
confiança, explicação e latências.

### O que observar

| Sintoma | Causa provável | Ajuste |
|---|---|---|
| `IMAGEM REJEITADA: blur_detected` | foto tremida / desfocada | melhor foco; ou baixar `MIN_SHARPNESS` em `app/vision/processor.py` |
| `IMAGEM REJEITADA: too_dark` / `too_bright` | iluminação | ajustar luz; ou os limiares de brilho no mesmo ficheiro |
| enunciado/opções incompletos | OCR falhou (texto pequeno, ângulo) | foto mais próxima e frontal; ou modo A (visão) |
| resposta errada | modelo fraco para o tema | modelo maior (`qwen2.5:7b` > `phi3.5`), ou modo A |
| demora > 30 s | inferência em CPU | normal sem GPU; ver README |

## Testar com a webcam + interface (fluxo real)

```bash
# .env: CAMERA_TYPE=usb, CAMERA_DEVICE=0
python -m app
```

Abre `http://localhost:8080/` no PC e `http://<ip-do-pc>:8080/` no telemóvel
(mesma Wi-Fi; abrir a porta 8080 na firewall do Windows).

- Aponta a webcam à tela com a questão, usa o preview para enquadrar.
- Carrega em **Capturar**. A resposta aparece nos dois ecrãs via WebSocket.

## Usar a câmera do telemóvel (CAMERA_TYPE=browser)

O browser só dá acesso à câmera em `localhost` ou **HTTPS**. Para o telemóvel:

```bash
# .env: HTTPS=true   (CAMERA_TYPE pode ser qualquer — troca-se na UI)
python -m app
```

No arranque são impressos os URLs `https://...`. No telemóvel abre
`https://<ip-do-pc>:8080/` (o mostrado para a tua LAN, ex: `192.168.1.4`).

1. O telemóvel avisa **"ligação não privada / certificado não confiável"** —
   é o certificado self-signed. Escolhe *Avançado → Continuar*.
2. Na interface, no seletor de câmera escolhe **"Câmera deste dispositivo"** e
   carrega **Usar**. Permite o acesso à câmera quando o browser pedir.
3. Aponta a câmera do telemóvel à questão e carrega **Capturar**.

O certificado é gerado uma vez em `certs/` e cobre `localhost` + os IPs da LAN.

## Recolher exemplos para calibração

Guarda 10-20 fotos representativas (ângulos, luz, tipos de questão) numa pasta.
Corre `scripts/test_image.py` em cada uma e anota o que falha. Com esse conjunto
podemos afinar os limiares e o prompt com dados reais em vez de palpites.
