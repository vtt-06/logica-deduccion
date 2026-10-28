/* Lógica — service worker de la aplicación instalable (PWA).
   Estrategia: red primero para no servir versiones antiguas; si no hay
   conexión, se usa la copia guardada.  Las llamadas a /api/ nunca se
   cachean. */
const CACHE = "logica-2.2.0";
const RECURSOS = [
  "/",
  "/index.html",
  "/styles.css",
  "/app.js",
  "/favicon.svg",
  "/manifest.json",
  "/icono-192.png",
  "/icono-512.png",
  "/icono-180.png",
  "/icono-maskable-512.png",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(RECURSOS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(
        claves.filter((clave) => clave !== CACHE)
          .map((clave) => caches.delete(clave))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const peticion = evento.request;
  if (peticion.method !== "GET") return;

  const url = new URL(peticion.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  evento.respondWith((async () => {
    try {
      const respuesta = await fetch(peticion);
      if (respuesta && respuesta.ok) {
        const copia = respuesta.clone();
        caches.open(CACHE).then((cache) => cache.put(peticion, copia));
      }
      return respuesta;
    } catch (error) {
      const guardada = await caches.match(peticion);
      if (guardada) return guardada;
      if (peticion.mode === "navigate") {
        const inicio = await caches.match("/index.html");
        if (inicio) return inicio;
      }
      throw error;
    }
  })());
});
