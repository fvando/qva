// Question Vision Assistant — interface mobile (TASK-011).
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
      setDot("camera", body.camera === true ? "ok" : body.camera === false ? "down" : "");
      setDot("llm", body.llm === true ? "ok" : body.llm === false ? "down" : "");
    } catch (e) {
      setDot("server", "down");
    }
  }
  refreshHealth();
  setInterval(refreshHealth, 15000);

  // -- Preview ---------------------------------------------------------
  var img = $("preview-img");
  var live = $("live");
  function showSnapshot() { img.src = "/api/camera/frame?t=" + Date.now(); }
  function refreshPreview() {
    if (live.checked) img.src = "/api/camera/stream?t=" + Date.now();
    else showSnapshot();
  }
  live.addEventListener("change", refreshPreview);
  showSnapshot();

  // -- Escolha de câmera ------------------------------------------------
  var kindSel = $("camera-kind");
  var usbSel = $("camera-usb");
  var urlInput = $("camera-url");
  var applyBtn = $("camera-apply");
  var camMsg = $("camera-msg");

  function updatePickerFields() {
    var k = kindSel.value;
    usbSel.hidden = k !== "usb";
    urlInput.hidden = k === "usb";
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
      // reflete a câmera ativa
      var a = data.active || {};
      if (a.type) {
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
    var target = kind === "usb" ? usbSel.value : urlInput.value.trim();
    camMsg.dataset.kind = "";
    camMsg.textContent = "a mudar de câmera…";
    applyBtn.disabled = true;
    try {
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

  // Polling de fallback entre eventos intermédios (processing_image / solving),
  // que o pipeline percorre depressa; garante feedback mesmo se um evento
  // se perder.
  btn.addEventListener("click", async function () {
    resetCards();
    setState("capturing");
    try {
      var r = await fetch("/api/capture", { method: "POST" });
      var capture_id = (await r.json()).capture_id;
      pollUntilDone(capture_id);
    } catch (e) {
      setState("error");
      $("error-text").textContent = "Falha ao iniciar a captura.";
      show("error-card");
    }
  });

  async function pollUntilDone(id) {
    for (var i = 0; i < 60; i++) {
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

  setState("idle");
})();
