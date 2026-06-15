// Service Worker: офлайн-кэширование статики и страниц.
const CACHE = 'erp-cache-v1';
const STATIC_ASSETS = [
  '/', '/wms', '/production', '/logistics', '/tree', '/chat', '/infrastructure', '/shift-summary',
  '/static/polyhedron.js', '/static/simulation.js', '/static/fx.js',
  '/static/autosave.js', '/static/offline-queue.js', '/static/resilience.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js',
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then((c) => Promise.allSettled(STATIC_ASSETS.map((u) => c.add(u).catch(() => null))))
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);

  // только GET кэшируем
  if (req.method !== 'GET') return;

  // health не кэшируем
  if (url.pathname === '/api/health') return;

  // API: network-first
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match(req).then((r) => r || new Response('{"offline":true}', { headers: { 'Content-Type': 'application/json' } })))
    );
    return;
  }

  // статика и страницы: cache-first + фоновое обновление
  e.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => cached);
      return cached || network;
    })
  );
});
