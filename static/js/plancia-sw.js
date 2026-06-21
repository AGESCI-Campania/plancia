/* Plancia Service Worker — v2 (Fase 6: Background Sync)
 *
 * Strategie di caching:
 *   /api/diari/**  GET  → stale-while-revalidate  (dati moduli, leggibili offline)
 *   /static/**          → stale-while-revalidate
 *   navigazione HTML    → network-first, fallback cache, fallback /offline/
 *   /api/soci/,
 *   /admin/, /media/**  → network-only (dati live / sensibili)
 *   PUT / POST / PATCH  → sempre rete (le scritture offline passano da IndexedDB — Fase 5)
 *
 * Background Sync:
 *   Quando il browser rileva che la connessione è tornata, lancia l'evento `sync`
 *   con tag `plancia-sync`. Il SW lo riceve e lo invia ai client aperti affinché
 *   plancia-sync.js esegua la replica dalla coda IndexedDB.
 */

const CACHE_PREFIX  = 'plancia';
const CACHE_VERSION = 'v5'; // bump: release v2.0.0
const STATIC_CACHE  = `${CACHE_PREFIX}-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `${CACHE_PREFIX}-dynamic-${CACHE_VERSION}`;
const API_CACHE     = `${CACHE_PREFIX}-api-${CACHE_VERSION}`;
const OFFLINE_URL   = '/offline/';
const ALL_CACHES    = [STATIC_CACHE, DYNAMIC_CACHE, API_CACHE];

// --- Install: pre-cacha la pagina offline --------------------------------
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.add(OFFLINE_URL))
      .then(() => self.skipWaiting())
  );
});

// --- Activate: elimina le cache delle versioni precedenti ----------------
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

/** Endpoint JSON dei moduli diario — GET sicuri da cachare per uso offline. */
function isApiDiari(url) {
  return /^\/api\/diari\/\d+\//.test(url.pathname);
}

function isStaticAsset(url) {
  return url.pathname.startsWith('/static/') || url.pathname === '/favicon.ico';
}

/** Percorsi che devono sempre andare in rete (dati live / sensibili). */
function isNetworkOnly(url) {
  return (
    url.pathname.startsWith('/api/') ||       // /api/soci/ e altri endpoint live
    url.pathname.startsWith('/admin/') ||
    url.pathname.startsWith('/media/') ||
    url.pathname.startsWith('/accounts/') ||  // login/logout/password: CSRF token sempre fresco
    url.pathname.startsWith('/allauth/') ||   // social auth callbacks
    url.pathname === '/offline/' ||
    url.pathname === '/serviceworker.js' ||
    url.pathname === '/manifest.json'
  );
}

// --- Background Sync: relay ai client aperti ------------------------------
// La logica di sync (IDB + PUT) vive in plancia-sync.js nel contesto pagina.
// Il SW si limita a segnalare ai client che devono eseguire la sync.
self.addEventListener('sync', event => {
  if (event.tag !== 'plancia-sync') return;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: false })
      .then(clients => {
        clients.forEach(client =>
          client.postMessage({ type: 'plancia:sync-request' })
        );
      })
  );
});

// --- Fetch ----------------------------------------------------------------
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (!sameOrigin(url)) return;

  // Non-GET: sempre rete.
  // Le scritture offline (PUT moduli) sono gestite da IndexedDB in Fase 5.
  if (event.request.method !== 'GET') return;

  // API moduli diario: stale-while-revalidate con cache dedicata.
  // Serve i dati cached immediatamente (funziona offline), aggiorna in background.
  if (isApiDiari(url)) {
    event.respondWith(
      caches.open(API_CACHE).then(cache =>
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

  // Network-only: admin, media, altri /api/, manifest, sw stesso.
  if (isNetworkOnly(url)) return;

  // Risorse statiche: stale-while-revalidate.
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

  // Navigazione HTML: network-first, fallback cache, fallback /offline/.
  // - Usiamo l'URL (stringa) come chiave di cache invece del Request object:
  //   evita che Vary:Cookie renda il match impossibile quando i cookie cambiano.
  // - event.waitUntil sul cache.put impedisce a iOS di uccidere il SW
  //   prima che il salvataggio in cache sia completato.
  if (event.request.mode === 'navigate') {
    const cacheKey = event.request.url;
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.ok) {
            const toCache = response.clone();
            event.waitUntil(
              caches.open(DYNAMIC_CACHE)
                .then(cache => cache.put(cacheKey, toCache))
                .catch(() => {})
            );
          }
          return response;
        })
        .catch(() =>
          caches.match(cacheKey, { ignoreVary: true })
            .then(cached => cached || caches.match(OFFLINE_URL))
        )
    );
    return;
  }

  // Tutto il resto: network-first senza fallback offline.
  event.respondWith(
    fetch(event.request)
      .catch(() => caches.match(event.request))
  );
});
