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

  // -- Captura ------------------------------------------------------------
  const btn = document.getElementById("capture");
  btn.disabled = false;
  btn.addEventListener("click", async function () {
    btn.disabled = true;
    btn.textContent = "A processar…";
    try {
      const r = await fetch("/api/capture", { method: "POST" });
      const { capture_id } = await r.json();
      // Polling simples até o WebSocket entrar (TASK-010).
      let done = false;
      while (!done) {
        await new Promise((res) => setTimeout(res, 500));
        const s = await (await fetch("/api/capture/" + capture_id)).json();
        if (s.status === "completed" || s.status === "error") {
          done = true;
          console.log("resultado:", s);
        }
      }
    } finally {
      btn.disabled = false;
      btn.textContent = "Capturar nova questão";
    }
  });
})();
