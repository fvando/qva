/* Question Vision Assistant — service worker.
 *
 * Estratégia:
 *  - Shell da app (HTML/CSS/JS/ícones): cache-first, atualiza em background.
 *    Faz a app abrir instantaneamente e sobreviver a um servidor a reiniciar.
 *  - API, WebSocket, preview da câmera, LLM: NUNCA em cache — sempre da rede.
 *    Uma resposta de questão em cache seria pior que erro nenhum.
 */

var CACHE = "qva-shell-v2";
var SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return c.addAll(SHELL);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE; }).map(function (k) {
          return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

function isShell(url) {
  return SHELL.indexOf(url.pathname) !== -1;
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;

  var url = new URL(req.url);

  // Nunca cachear nada dinâmico.
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/ws") ||
    url.pathname.startsWith("/health")
  ) {
    return; // deixa passar para a rede
  }

  if (isShell(url)) {
    // cache-first + revalidação em background
    e.respondWith(
      caches.match(req).then(function (cached) {
        var network = fetch(req)
          .then(function (res) {
            if (res && res.ok) {
              var copy = res.clone();
              caches.open(CACHE).then(function (c) { c.put(req, copy); });
            }
            return res;
          })
          .catch(function () { return cached; });
        return cached || network;
      })
    );
  }
});
