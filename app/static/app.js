// Question Vision Assistant — interface mobile (TASK-011 + câmera do browser).
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  // -- Semáforo de status ------------------------------------------------
  function setDot(service, state) {
    var el = document.querySelector('.dot[data-service="' + service + '"]');
    if (el) el.dataset.state = state;
  }

  async function refreshHealth() {
    try {
      var res = await fetch("/health");
      var body = await res.json();
      setDot("server", res.ok ? "ok" : "down");
      if (!browserMode) {
        setDot("camera", body.camera === true ? "ok" : body.camera === false ? "down" : "");
      }
      setDot("llm", body.llm === true ? "ok" : body.llm === false ? "down" : "");
    } catch (e) {
      setDot("server", "down");
    }
  }
  refreshHealth();
  setInterval(refreshHealth, 15000);

  // -- Seletor de modelo LLM + estado do serviço --------------------
  var modelSelect = $("model-select");
  var llmBadge = $("llm-badge");

  async function loadLlmStatus() {
    try {
      var s = await (await fetch("/api/llm/status")).json();
      var label = (s.mode || "").toUpperCase();
      if (s.cloud) label += " · cloud";
      else label += " · local";
      llmBadge.textContent = label;
      llmBadge.dataset.kind = s.cloud ? "cloud" : "";
      llmBadge.hidden = false;
    } catch (e) { /* ignora */ }
  }
  loadLlmStatus();

  async function loadModels() {
    try {
      var data = await (await fetch("/api/llm/models")).json();
      modelSelect.innerHTML = "";
      var models = data.models || [];
      models.forEach(function (m) {
        var o = document.createElement("option");
        o.value = m;
        o.textContent = m;
        modelSelect.appendChild(o);
      });
      if (!models.length && data.active) {
        var o = document.createElement("option");
        o.value = data.active;
        o.textContent = data.active;
        modelSelect.appendChild(o);
      }
      if (data.active) modelSelect.value = data.active;
      // desativa se só há 1 opção (nada para escolher)
      modelSelect.disabled = modelSelect.options.length < 2;
    } catch (e) {
      modelSelect.disabled = true;
    }
  }
  loadModels();

  modelSelect.addEventListener("change", async function () {
    var prev = modelSelect.value;
    modelSelect.disabled = true;
    try {
      var r = await fetch("/api/llm/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: modelSelect.value }),
      });
      if (!r.ok) { modelSelect.value = prev; }
    } catch (e) {
      modelSelect.value = prev;
    } finally {
      modelSelect.disabled = false;
    }
  });

  // -- Preview: imagem do servidor OU vídeo do dispositivo --------------
  var img = $("preview-img");
  var video = $("browser-video");
  var live = $("live");
  var browserMode = false;          // true = câmera deste dispositivo
  var mediaStream = null;
  var facingMode = "environment";   // câmera traseira por omissão

  function showSnapshot() { img.src = "/api/camera/frame?t=" + Date.now(); }
  function refreshPreview() {
    if (browserMode) return;
    if (live.checked) img.src = "/api/camera/stream?t=" + Date.now();
    else showSnapshot();
  }
  live.addEventListener("change", refreshPreview);

  async function startBrowserCamera() {
    stopBrowserCamera();
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facingMode } },
        audio: false,
      });
    } catch (e) {
      camMsg.dataset.kind = "error";
      camMsg.textContent = "sem acesso à câmera do dispositivo: " + e.name;
      setDot("camera", "down");
      return false;
    }
    video.srcObject = mediaStream;
    img.hidden = true;
    video.hidden = false;
    $("browser-switch").hidden = false;
    live.parentElement.style.visibility = "hidden";
    browserMode = true;
    setDot("camera", "ok");
    return true;
  }

  function stopBrowserCamera() {
    if (mediaStream) {
      mediaStream.getTracks().forEach(function (t) { t.stop(); });
      mediaStream = null;
    }
    video.srcObject = null;
    video.hidden = true;
    img.hidden = false;
    $("browser-switch").hidden = true;
    live.parentElement.style.visibility = "";
    browserMode = false;
  }

  $("browser-switch").addEventListener("click", function () {
    facingMode = facingMode === "environment" ? "user" : "environment";
    startBrowserCamera();
  });

  // Captura um frame do <video> como JPEG (Blob).
  function grabVideoJpeg() {
    return new Promise(function (resolve, reject) {
      var w = video.videoWidth, h = video.videoHeight;
      if (!w || !h) { reject(new Error("vídeo ainda sem imagem")); return; }
      var canvas = document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      canvas.getContext("2d").drawImage(video, 0, 0, w, h);
      canvas.toBlob(function (blob) {
        if (blob) resolve(blob); else reject(new Error("falha ao codificar frame"));
      }, "image/jpeg", 0.9);
    });
  }

  // -- Escolha de câmera ------------------------------------------------
  var kindSel = $("camera-kind");
  var usbSel = $("camera-usb");
  var urlInput = $("camera-url");
  var applyBtn = $("camera-apply");
  var camMsg = $("camera-msg");

  function updatePickerFields() {
    var k = kindSel.value;
    usbSel.hidden = k !== "usb";
    urlInput.hidden = k === "usb" || k === "browser";
  }
  kindSel.addEventListener("change", updatePickerFields);

  async function loadDevices() {
    try {
      var data = await (await fetch("/api/camera/devices")).json();
      usbSel.innerHTML = "";
      (data.devices || []).forEach(function (d) {
        var o = document.createElement("option");
        o.value = d.target;
        o.textContent = d.label;
        usbSel.appendChild(o);
      });
      if (!data.devices || !data.devices.length) {
        var o = document.createElement("option");
        o.value = "0";
        o.textContent = "Câmera 0 (padrão)";
        usbSel.appendChild(o);
      }
      var a = data.active || {};
      if (a.type && a.type !== "browser") {
        kindSel.value = a.type === "file" ? "usb" : a.type;
        if (a.type === "usb") usbSel.value = a.target;
        else urlInput.value = a.target || "";
      }
      updatePickerFields();
    } catch (e) {
      camMsg.textContent = "não foi possível listar câmeras";
    }
  }
  loadDevices();

  applyBtn.addEventListener("click", async function () {
    var kind = kindSel.value;
    camMsg.dataset.kind = "";
    applyBtn.disabled = true;

    try {
      if (kind === "browser") {
        camMsg.textContent = "a pedir acesso à câmera…";
        var ok = await startBrowserCamera();
        if (ok) {
          // Diz ao servidor para usar a fonte 'browser' (frame vem por upload).
          await fetch("/api/camera/select", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind: "browser", target: "" }),
          });
          camMsg.dataset.kind = "ok";
          camMsg.textContent = "a usar a câmera deste dispositivo.";
        }
        return;
      }

      // Câmera do servidor (usb / rtsp / http)
      stopBrowserCamera();
      var target = kind === "usb" ? usbSel.value : urlInput.value.trim();
      camMsg.textContent = "a mudar de câmera…";
      var r = await fetch("/api/camera/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: kind, target: target }),
      });
      if (!r.ok) {
        var err = await r.json();
        camMsg.dataset.kind = "error";
        camMsg.textContent = "erro: " + (err.detail || r.status);
      } else {
        camMsg.dataset.kind = "ok";
        camMsg.textContent = "câmera alterada.";
        setDot("camera", "ok");
        refreshPreview();
      }
    } catch (e) {
      camMsg.dataset.kind = "error";
      camMsg.textContent = "falha ao contactar o servidor";
    } finally {
      applyBtn.disabled = false;
    }
  });

  // -- Estados visuais (secção 17) -------------------------------------
  var STATE_LABEL = {
    idle: "Pronto para capturar.",
    capturing: "A capturar imagem…",
    processing_image: "A processar imagem…",
    extracting_question: "A identificar a questão…",
    solving: "A resolver…",
    completed: "Concluído.",
    error: "Ocorreu um erro.",
  };
  var banner = $("state-banner");
  var btn = $("capture");

  function setState(state) {
    banner.dataset.state = state;
    banner.textContent = STATE_LABEL[state] || state;
    var busy = ["capturing", "processing_image", "extracting_question", "solving"].indexOf(state) !== -1;
    btn.disabled = busy;
    btn.textContent = busy ? "A processar…" : "Capturar nova questão";
  }

  function hide(id) { $(id).hidden = true; }
  function show(id) { $(id).hidden = false; }

  function renderQuestion(q) {
    if (!q) return;
    $("question-type").textContent = q.type || "";
    $("question-text").textContent = q.question || "";
    var ul = $("question-options");
    ul.innerHTML = "";
    Object.keys(q.options || {}).forEach(function (k) {
      var li = document.createElement("li");
      li.innerHTML = "<b>" + k + ")</b> " + q.options[k];
      ul.appendChild(li);
    });
    show("question-card");
  }

  function renderAnswer(r, timing) {
    if (!r) return;
    var letter = r.answer || "";
    var text = r.answer_text ? " " + r.answer_text : "";
    $("answer-line").textContent = letter ? letter + ")" + text : text.trim() || "—";
    $("confidence").textContent =
      r.confidence != null ? "Confiança: " + Math.round(r.confidence * 100) + "%" : "";
    $("explanation").textContent = r.explanation || "";
    $("ambiguous").hidden = !r.ambiguous;
    if (timing) {
      $("timing").textContent = "Total: " + Math.round(timing.total_ms) + " ms " +
        "(LLM " + Math.round(timing.llm_ms) + " ms)";
    }
    show("answer-card");
  }

  function resetCards() {
    hide("question-card");
    hide("answer-card");
    hide("error-card");
  }

  // -- WebSocket: eventos do pipeline sem polling ------------------------
  function connectWS() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var socket = new WebSocket(proto + "//" + location.host + "/ws");
    socket.onmessage = function (ev) {
      var msg = JSON.parse(ev.data);
      var event = msg.event;
      var data = msg.data || {};
      if (event === "capture_started") {
        resetCards();
        setState("capturing");
      } else if (event === "question_detected") {
        setState("extracting_question");
        renderQuestion(data.question);
      } else if (event === "answer_ready") {
        var resp = data.response || {};
        renderQuestion(resp.question);
        renderAnswer(resp.result, resp.timing);
        setState("completed");
      } else if (event === "error") {
        $("error-text").textContent = data.reason || "erro desconhecido";
        show("error-card");
        setState("error");
      }
    };
    socket.onclose = function () { setTimeout(connectWS, 2000); };
  }
  connectWS();

  btn.addEventListener("click", async function () {
    resetCards();
    setState("capturing");
    try {
      // No modo browser, envia primeiro o frame da câmera do dispositivo.
      if (browserMode) {
        var blob = await grabVideoJpeg();
        var up = await fetch("/api/camera/upload-frame", {
          method: "POST",
          headers: { "Content-Type": "image/jpeg" },
          body: blob,
        });
        if (!up.ok) throw new Error("falha ao enviar o frame");
      }
      var r = await fetch("/api/capture", { method: "POST" });
      var capture_id = (await r.json()).capture_id;
      pollUntilDone(capture_id);
    } catch (e) {
      setState("error");
      $("error-text").textContent = "Falha ao iniciar a captura: " + (e.message || e);
      show("error-card");
    }
  });

  async function pollUntilDone(id) {
    for (var i = 0; i < 90; i++) {
      await new Promise(function (res) { setTimeout(res, 700); });
      var s;
      try {
        s = await (await fetch("/api/capture/" + id)).json();
      } catch (e) {
        continue;
      }
      if (["capturing", "processing_image", "extracting_question", "solving"].indexOf(s.status) !== -1) {
        setState(s.status);
      }
      if (s.status === "completed") {
        renderQuestion(s.question);
        renderAnswer(s.result, s.timing);
        setState("completed");
        return;
      }
      if (s.status === "error") {
        $("error-text").textContent = s.error || "erro desconhecido";
        show("error-card");
        setState("error");
        return;
      }
    }
  }

  // Se não há câmera no servidor, arranca já no modo browser.
  (async function autoPickCamera() {
    try {
      var data = await (await fetch("/api/camera/devices")).json();
      var active = (data.active || {}).type;
      if (active === "browser" || !(data.devices || []).length) {
        kindSel.value = "browser";
        updatePickerFields();
      }
    } catch (e) { /* ignora */ }
  })();

  showSnapshot();
  setState("idle");
})();
