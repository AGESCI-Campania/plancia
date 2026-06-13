/* plancia-sync.js — replica automatica della coda offline + gestione sessione scaduta.
 *
 * Dipende da: plancia-idb.js (caricato prima)
 *
 * Trigger di sincronizzazione:
 *   1. Evento window `online`         — connessione riacquistata
 *   2. Messaggio SW `plancia:sync-request` — Background Sync API (Chrome/Edge)
 *   3. DOMContentLoaded               — pendenti in coda + online + autenticati
 *
 * Gestione sessione:
 *   - 401 durante sync/save → accoda, mostra banner "Accedi per sincronizzare"
 *   - Login riuscito → DOMContentLoaded rileva PLANCIA_AUTENTICATO=true, pulisce il
 *     flag e rilancia PlanciaSync.run() automaticamente
 *
 * API pubblica (window.PlanciaSync):
 *   run() → Promise<void>
 *
 * Flusso per ogni item nella coda:
 *   200 → rimuove da IDB, aggiorna SW cache
 *   401 → ferma il ciclo, mostra banner "sessione scaduta"
 *   409 → lascia in coda (conflitto versione, intervento manuale)
 *   4xx → rimuove da IDB (irrecuperabile)
 *   errore rete → interrompe il ciclo, riprova al prossimo trigger
 */

(function () {
  'use strict';

  var API_CACHE_NAME    = 'plancia-api-v2';
  var SESSION_EXPIRED_K = 'planciaSessionExpired';

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function getCsrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function showToast(title, body, type) {
    var el = document.getElementById('plancia-toast');
    if (!el || !window.bootstrap) return;
    document.getElementById('plancia-toast-title').textContent = title;
    document.getElementById('plancia-toast-body').textContent  = body;
    el.className = 'toast border-0 text-bg-' + (type || 'secondary');
    bootstrap.Toast.getOrCreateInstance(el, { delay: 8000 }).show();
  }

  async function refreshApiCache(url, freshData) {
    if (!window.caches) return;
    try {
      var cache = await caches.open(API_CACHE_NAME);
      await cache.put(url, new Response(JSON.stringify(freshData), {
        headers: { 'Content-Type': 'application/json' },
      }));
    } catch (e) { /* best-effort */ }
  }

  // ---------------------------------------------------------------------------
  // Banner "sessione scaduta"
  // ---------------------------------------------------------------------------

  function showAuthBanner(count) {
    var banner  = document.getElementById('offline-auth-banner');
    var countEl = document.getElementById('auth-banner-count');
    if (!banner) return;
    if (countEl) countEl.textContent = count;
    banner.classList.remove('d-none');
  }

  function hideAuthBanner() {
    var banner = document.getElementById('offline-auth-banner');
    if (banner) banner.classList.add('d-none');
  }

  function markSessionExpired() {
    sessionStorage.setItem(SESSION_EXPIRED_K, '1');
  }

  function clearSessionExpired() {
    sessionStorage.removeItem(SESSION_EXPIRED_K);
  }

  function isSessionExpiredFlagged() {
    return !!sessionStorage.getItem(SESSION_EXPIRED_K);
  }

  // Aggiorna il banner al cambio del conteggio pendenti.
  document.addEventListener('plancia:pending-count', function (e) {
    if (e.detail === 0) {
      clearSessionExpired();
      hideAuthBanner();
    } else if (isSessionExpiredFlagged() && !window.PLANCIA_AUTENTICATO) {
      showAuthBanner(e.detail);
    }
  });

  // Evento lanciato da questo modulo o da plancia-moduli-offline.js quando riceve 401.
  document.addEventListener('plancia:session-expired', function () {
    markSessionExpired();
    if (window.PlanciaIdb) {
      PlanciaIdb.count().then(function (n) {
        if (n > 0) showAuthBanner(n);
      }).catch(function () {});
    }
  });

  // ---------------------------------------------------------------------------
  // Sincronizzazione
  // ---------------------------------------------------------------------------

  var _running = false;

  async function run() {
    if (_running || !window.PlanciaIdb || !navigator.onLine) return;
    _running = true;

    try {
      var items = await PlanciaIdb.getAll();
      if (items.length === 0) return;

      var synced    = 0;
      var conflicts = 0;

      for (var i = 0; i < items.length; i++) {
        var item = items[i];

        try {
          var resp = await fetch(item.url, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken':  getCsrf(),
            },
            body: JSON.stringify(item.payload),
          });

          if (resp.ok) {
            var result = await resp.json();
            await refreshApiCache(item.url, result);
            await PlanciaIdb.remove(item.id);
            synced++;

          } else if (resp.status === 401) {
            // Sessione scaduta: ferma il ciclo e mostra il banner.
            // Gli item rimangono in coda; il sync ripartirà dopo il login.
            document.dispatchEvent(new CustomEvent('plancia:session-expired'));
            break;

          } else if (resp.status === 409) {
            // Conflitto di versione: l'utente deve risolvere manualmente.
            conflicts++;

          } else {
            // 400, 403, ecc. — irrecuperabile, rimuovi.
            await PlanciaIdb.remove(item.id);
          }

        } catch (networkErr) {
          // Ancora offline o errore transitorio — riprova al prossimo trigger.
          break;
        }
      }

      // Toast con il risultato (solo se nessuna interruzione per 401/rete)
      if (synced > 0 && conflicts === 0) {
        clearSessionExpired();
        hideAuthBanner();
        showToast(
          'Sincronizzazione completata',
          synced === 1 ? '1 modifica sincronizzata.' : synced + ' modifiche sincronizzate.',
          'success'
        );
      } else if (synced > 0 && conflicts > 0) {
        showToast(
          'Sincronizzazione parziale',
          synced + ' sincronizzat' + (synced === 1 ? 'a' : 'e') + ', ' +
            conflicts + ' con conflitto. Apri il modulo e salva di nuovo per risolvere.',
          'warning'
        );
      } else if (synced === 0 && conflicts > 0) {
        showToast(
          'Conflitti da risolvere',
          conflicts === 1
            ? '1 modifica in conflitto: apri il modulo e salva di nuovo.'
            : conflicts + ' modifiche in conflitto: apri i moduli e salva di nuovo.',
          'danger'
        );
      }

    } finally {
      _running = false;
    }
  }

  // ---------------------------------------------------------------------------
  // Trigger
  // ---------------------------------------------------------------------------

  // 1. Connessione riacquistata mentre la pagina è aperta.
  window.addEventListener('online', function () { run(); });

  // 2. Background Sync API (Chrome/Edge): il SW relay il trigger.
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', function (ev) {
      if (ev.data && ev.data.type === 'plancia:sync-request') run();
    });
  }

  // 3. Al caricamento della pagina: controlla stato auth e pendenti.
  document.addEventListener('DOMContentLoaded', function () {
    // Se autenticati: cancella il flag "sessione scaduta" e nascondi il banner.
    if (window.PLANCIA_AUTENTICATO) {
      clearSessionExpired();
      hideAuthBanner();
    }

    // Se c'è il flag (sessione scaduta in precedenza) e non siamo autenticati: mostra il banner.
    if (isSessionExpiredFlagged() && !window.PLANCIA_AUTENTICATO && window.PlanciaIdb) {
      PlanciaIdb.count().then(function (n) {
        if (n > 0) showAuthBanner(n);
      }).catch(function () {});
    }

    // Se autenticati, online e ci sono pendenti: rilancia sync (scenario post-login).
    if (window.PLANCIA_AUTENTICATO && navigator.onLine && window.PlanciaIdb) {
      PlanciaIdb.count().then(function (n) { if (n > 0) run(); }).catch(function () {});
    }
  });

  window.PlanciaSync = { run: run };

})();
