// QVA — app de consulta (estilo chat). Só recebe respostas via WebSocket.
(function () {
  "use strict";

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }

  var $ = function (id) { return document.getElementById(id); };
  var feed = $("feed");
  var tplMsg = $("tpl-msg");
  var tplErr = $("tpl-error");

  // Evita duplicar a mesma resposta (o servidor reenvia a última ao ligar).
  var seen = Object.create(null);

  function setLink(state, text) {
    var dot = document.querySelector('.dot[data-service="link"]');
    if (dot) dot.dataset.state = state;
    $("link-text").textContent = text;
  }

  function nowLabel() {
    var d = new Date();
    return d.toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" });
  }

  function atBottom() {
    return window.innerHeight + window.scrollY >= document.body.scrollHeight - 80;
  }

  function append(node) {
    var empty = $("feed-empty");
    if (empty) empty.remove();
    var stick = atBottom();
    feed.appendChild(node);
    if (stick) window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }

  function addAnswer(resp) {
    var id = resp.id;
    if (id && seen[id]) return;
    if (id) seen[id] = true;

    var q = resp.question || {};
    var r = resp.result || {};
    var t = resp.timing || {};

    var el = tplMsg.content.firstElementChild.cloneNode(true);
    var letter = r.answer || "";
    var text = r.answer_text ? " " + r.answer_text : "";
    el.querySelector(".msg-answer").textContent =
      letter ? letter + ")" + text : (text.trim() || "—");
    el.querySelector(".msg-conf").textContent =
      r.confidence != null ? Math.round(r.confidence * 100) + "%" : "";
    el.querySelector(".msg-question").textContent = q.question || "";

    var ul = el.querySelector(".msg-options");
    Object.keys(q.options || {}).forEach(function (k) {
      var li = document.createElement("li");
      var b = document.createElement("b");
      b.textContent = k + ") ";
      li.appendChild(b);
      li.appendChild(document.createTextNode(q.options[k]));
      if (k === r.answer) li.className = "is-answer";
      ul.appendChild(li);
    });

    el.querySelector(".msg-expl").textContent = r.explanation || "";
    el.querySelector(".msg-time").textContent =
      nowLabel() + (t.total_ms ? " · " + Math.round(t.total_ms / 1000) + "s" : "");
    append(el);
  }

  function addError(reason, capture_id) {
    if (capture_id && seen["err:" + capture_id]) return;
    if (capture_id) seen["err:" + capture_id] = true;
    var el = tplErr.content.firstElementChild.cloneNode(true);
    el.querySelector(".msg-question").textContent = reason || "erro desconhecido";
    el.querySelector(".msg-time").textContent = nowLabel();
    append(el);
  }

  function setPending(on) {
    var p = $("pending");
    if (on && !p) {
      var el = document.createElement("p");
      el.id = "pending";
      el.className = "feed-pending";
      el.textContent = "A resolver a nova questão…";
      feed.appendChild(el);
      if (atBottom()) window.scrollTo({ top: document.body.scrollHeight });
    } else if (!on && p) {
      p.remove();
    }
  }

  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var socket = new WebSocket(proto + "//" + location.host + "/ws");

    socket.onopen = function () { setLink("ok", "ligado"); };

    socket.onmessage = function (ev) {
      var msg = JSON.parse(ev.data);
      var d = msg.data || {};
      if (msg.event === "capture_started") {
        setPending(true);
      } else if (msg.event === "answer_ready") {
        setPending(false);
        addAnswer(d.response || {});
      } else if (msg.event === "error") {
        setPending(false);
        addError(d.reason, d.capture_id);
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
