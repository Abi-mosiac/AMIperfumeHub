const CACHE_NAME = "amiperfumehub-shell-v1";
const SHELL = [
  "/",
  "/static/manifest.webmanifest",
  "/static/assets/css/style.css",
  "/static/assets/css/forms.css",
  "/static/js/app.js",
  "/static/assets/perfume-placeholder.svg",
  "/static/assets/icons/icon-192.svg",
  "/static/assets/icons/icon-512.svg"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
  )));
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/auth/") || url.pathname.startsWith("/admin/") || url.pathname.startsWith("/orders") || url.pathname.startsWith("/cart") || url.pathname.startsWith("/vendor/") || url.pathname.startsWith("/products")) return;

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/")));
    return;
  }
  event.respondWith(caches.match(request, { ignoreSearch: true }).then(cached => cached || fetch(request)));
});
