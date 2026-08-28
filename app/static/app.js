// Question Vision Assistant — cliente mínimo (TASK-001). Lógica real: TASK-011.
(async function () {
  "use strict";

  function setDot(service, state) {
    const el = document.querySelector(`.dot[data-service="${service}"]`);
    if (el) el.dataset.state = state;
  }

  try {
    const res = await fetch("/health");
    const body = await res.json();
    setDot("server", res.ok ? "ok" : "down");
    setDot("camera", body.camera === true ? "ok" : body.camera === false ? "down" : "unknown");
    setDot("llm", body.llm === true ? "ok" : body.llm === false ? "down" : "unknown");
  } catch (err) {
    setDot("server", "down");
  }
})();
