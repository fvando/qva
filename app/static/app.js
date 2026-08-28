// Question Vision Assistant — cliente mínimo (TASK-001). Lógica real: TASK-011.
(async function () {
  "use strict";

  function setDot(service, state) {
    const el = document.querySelector(`.dot[data-service="${service}"]`);
    if (el) el.dataset.state = state;
  }

  // -- Preview -------------------------------------------------------------
  const img = document.getElementById("preview-img");
  const live = document.getElementById("live");
  let refreshTimer = null;

  function showSnapshot() {
    img.src = "/api/camera/frame?t=" + Date.now();
  }
  function stopLive() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = null;
  }
  live.addEventListener("change", function () {
    if (live.checked) {
      img.src = "/api/camera/stream";
    } else {
      stopLive();
      showSnapshot();
    }
  });
  showSnapshot();

  try {
    const res = await fetch("/health");
    const body = await res.json();
    setDot("server", res.ok ? "ok" : "down");
    setDot("camera", body.camera === true ? "ok" : body.camera === false ? "down" : "unknown");
    setDot("llm", body.llm === true ? "ok" : body.llm === false ? "down" : "unknown");
  } catch (err) {
    setDot("server", "down");
  }

  // -- WebSocket: recebe eventos do pipeline sem polling (TASK-010) -------
  const btn = document.getElementById("capture");
  btn.disabled = false;

  function connectWS() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(proto + "//" + location.host + "/ws");
    socket.onmessage = function (ev) {
      const { event, data } = JSON.parse(ev.data);
      console.log("evento:", event, data);
      if (event === "capture_started") {
        btn.disabled = true;
        btn.textContent = "A processar…";
      }
      if (event === "answer_ready" || event === "error") {
        btn.disabled = false;
        btn.textContent = "Capturar nova questão";
      }
    };
    socket.onclose = function () {
      setTimeout(connectWS, 2000); // reconecta
    };
  }
  connectWS();

  btn.addEventListener("click", function () {
    fetch("/api/capture", { method: "POST" });
    // O resultado chega pelo WebSocket (answer_ready / error).
  });
})();
