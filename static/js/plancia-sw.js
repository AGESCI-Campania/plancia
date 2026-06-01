/* Plancia Service Worker
 * Strategia:
 *   /static/**        → stale-while-revalidate  (cache, poi aggiorna in background)
 *   navigazione HTML  → network-first, fallback cache, fallback /offline/
 *   /api/**, /admin/,
 *   /media/**         → network-only (dati sensibili / dinamici)
 */

const CACHE_PREFIX = 'plancia';
const CACHE_VERSION = 'v1';
const STATIC_CACHE  = `${CACHE_PREFIX}-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `${CACHE_PREFIX}-dynamic-${CACHE_VERSION}`;
const OFFLINE_URL   = '/offline/';
const ALL_CACHES    = [STATIC_CACHE, DYNAMIC_CACHE];

// --- Install: pre-cacha solo la pagina offline ----------------------------
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.add(OFFLINE_URL))
      .then(() => self.skipWaiting())
  );
});

// --- Activate: elimina versioni precedenti --------------------------------
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(k => k.startsWith(CACHE_PREFIX) && !ALL_CACHES.includes(k))
          .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// --- Helpers --------------------------------------------------------------
function sameOrigin(url) {
  return url.origin === self.location.origin;
}

function isStaticAsset(url) {
  return url.pathname.startsWith('/static/') || url.pathname === '/favicon.ico';
}

function isNetworkOnly(url) {
  return (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/admin/') ||
    url.pathname.startsWith('/media/') ||
    url.pathname === '/serviceworker.js' ||
    url.pathname === '/manifest.json'
  );
}

// --- Fetch ----------------------------------------------------------------
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (!sameOrigin(url)) return;
  if (isNetworkOnly(url)) return;

  // Risorse statiche: stale-while-revalidate
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.open(STATIC_CACHE).then(cache =>
        cache.match(event.request).then(cached => {
          const networkFetch = fetch(event.request).then(response => {
            if (response && response.ok) cache.put(event.request, response.clone());
            return response;
          }).catch(() => null);
          return cached || networkFetch;
        })
      )
    );
    return;
  }

  // Navigazione HTML: network-first, fallback cache, fallback /offline/
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.ok) {
            caches.open(DYNAMIC_CACHE)
              .then(cache => cache.put(event.request, response.clone()));
          }
          return response;
        })
        .catch(() =>
          caches.match(event.request)
            .then(cached => cached || caches.match(OFFLINE_URL))
        )
    );
    return;
  }

  // Tutto il resto: network-first senza offline fallback
  event.respondWith(
    fetch(event.request)
      .catch(() => caches.match(event.request))
  );
});
