// QVA — app de consulta. Só recebe respostas via WebSocket e mostra-as.
(function () {
  "use strict";

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }

  var $ = function (id) { return document.getElementById(id); };

  function setLink(state, text) {
    var dot = document.querySelector('.dot[data-service="link"]');
    if (dot) dot.dataset.state = state;
    $("link-text").textContent = text;
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
      var b = document.createElement("b");
      b.textContent = k + ") ";
      li.appendChild(b);
      li.appendChild(document.createTextNode(q.options[k]));
      ul.appendChild(li);
    });
    show("question-card");
    hide("idle");
  }

  function renderAnswer(r, timing) {
    if (!r) return;
    var letter = r.answer || "";
    var text = r.answer_text ? " " + r.answer_text : "";
    $("answer-line").textContent = letter ? letter + ")" + text : text.trim() || "—";
    $("confidence").textContent =
      r.confidence != null ? Math.round(r.confidence * 100) + "%" : "";
    $("explanation").textContent = r.explanation || "";
    $("ambiguous").hidden = !r.ambiguous;
    if (timing) {
      $("meta").textContent = "Resolvido em " + Math.round(timing.total_ms / 1000) + " s";
    }
    show("answer-card");
    hide("idle");
    if ($("answer-card").scrollIntoView) {
      $("answer-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function reset() {
    hide("question-card");
    hide("answer-card");
    hide("error-card");
  }

  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var socket = new WebSocket(proto + "//" + location.host + "/ws");

    socket.onopen = function () { setLink("ok", "ligado"); };

    socket.onmessage = function (ev) {
      var msg = JSON.parse(ev.data);
      var event = msg.event;
      var data = msg.data || {};

      if (event === "capture_started") {
        reset();
        show("idle");
        $("idle").textContent = "A resolver a nova questão…";
      } else if (event === "question_detected") {
        renderQuestion(data.question);
      } else if (event === "answer_ready") {
        var resp = data.response || {};
        renderQuestion(resp.question);
        renderAnswer(resp.result, resp.timing);
      } else if (event === "error") {
        reset();
        $("error-text").textContent = data.reason || "erro desconhecido";
        show("error-card");
        hide("idle");
      }
    };

    socket.onclose = function () {
      setLink("down", "sem ligação — a reconectar…");
      setTimeout(connect, 2000);
    };
    socket.onerror = function () { socket.close(); };
  }

  setLink("", "a ligar…");
  connect();
})();
