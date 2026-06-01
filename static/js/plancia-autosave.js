/* Plancia — autosave IndexedDB per i moduli del Diario.
 *
 * Qualsiasi <form data-autosave-key="..."> viene sorvegliato:
 *  - ripristino automatico all'apertura della pagina (se esiste bozza locale)
 *  - salvataggio su IndexedDB 2 s dopo l'ultima modifica
 *  - blocco del submit quando offline (con messaggio)
 *  - cancellazione della bozza dopo il submit riuscito
 *
 * Banner globale offline/online fisso in fondo alla pagina.
 */
(function () {
  'use strict';

  const DB_NAME    = 'plancia-offline';
  const DB_VERSION = 1;
  const STORE      = 'autosave';

  // ── IndexedDB helpers ────────────────────────────────────────────────────

  function openDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = e => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: 'key' });
        }
      };
      req.onsuccess = e => resolve(e.target.result);
      req.onerror   = e => reject(e.target.error);
    });
  }

  function dbGet(db, key) {
    return new Promise((resolve, reject) => {
      const req = db.transaction(STORE, 'readonly').objectStore(STORE).get(key);
      req.onsuccess = e => resolve(e.target.result);
      req.onerror   = e => reject(e.target.error);
    });
  }

  function dbPut(db, record) {
    return new Promise((resolve, reject) => {
      const req = db.transaction(STORE, 'readwrite').objectStore(STORE).put(record);
      req.onsuccess = () => resolve();
      req.onerror   = e => reject(e.target.error);
    });
  }

  function dbDelete(db, key) {
    return new Promise((resolve, reject) => {
      const req = db.transaction(STORE, 'readwrite').objectStore(STORE).delete(key);
      req.onsuccess = () => resolve();
      req.onerror   = e => reject(e.target.error);
    });
  }

  // ── Form serialization ───────────────────────────────────────────────────

  const SKIP_RE = /csrfmiddlewaretoken|-(TOTAL|INITIAL|MIN_NUM|MAX_NUM)_FORMS$/;

  function serializeForm(form) {
    const data = {};
    new FormData(form).forEach((v, k) => {
      if (SKIP_RE.test(k)) return;
      data[k] = v;
    });
    return data;
  }

  function restoreFormFields(form, data) {
    Object.entries(data).forEach(([k, v]) => {
      const escaped = k.replace(/([!"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, '\\$1');
      const el = form.querySelector(`[name="${escaped}"]`);
      if (!el) return;
      if (el.tagName === 'SELECT') {
        [...el.options].forEach(opt => { opt.selected = (opt.value === v); });
      } else if (el.type === 'checkbox' || el.type === 'radio') {
        el.checked = (el.value === v);
      } else {
        el.value = v;
      }
    });
  }

  // ── Banner per singolo form ──────────────────────────────────────────────

  function showFormBanner(form, msg, type) {
    let b = form.querySelector('.plancia-form-banner');
    if (!b) {
      b = document.createElement('div');
      b.className = 'plancia-form-banner alert mb-3 py-2 small';
      form.prepend(b);
    }
    b.className = `plancia-form-banner alert mb-3 py-2 small alert-${
      type === 'draft' ? 'warning' : type === 'ok' ? 'success' : 'secondary'
    }`;
    b.textContent = msg;
  }

  function hideFormBanner(form) {
    const b = form.querySelector('.plancia-form-banner');
    if (b) b.remove();
  }

  // ── Wiring di un singolo form ────────────────────────────────────────────

  async function wireForm(form, db) {
    const key = form.dataset.autosaveKey;

    // Ripristina bozza locale
    const saved = await dbGet(db, key);
    if (saved && saved.data) {
      restoreFormFields(form, saved.data);
      const ts    = new Date(saved.ts);
      const giorno = ts.toLocaleDateString('it-IT');
      const ora    = ts.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
      showFormBanner(form,
        `Bozza locale del ${giorno} alle ${ora} — modifica il testo o clicca Salva per confermare.`,
        'draft'
      );
    }

    // Autosave debounced (2 s dopo l'ultima modifica)
    let timer;
    form.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        await dbPut(db, { key, data: serializeForm(form), ts: Date.now() });
        showFormBanner(form, 'Bozza salvata localmente.', 'ok');
        setTimeout(() => hideFormBanner(form), 3000);
      }, 2000);
    });

    // Intercetta submit
    form.addEventListener('submit', async e => {
      clearTimeout(timer);

      if (!navigator.onLine) {
        e.preventDefault();
        await dbPut(db, { key, data: serializeForm(form), ts: Date.now() });
        showFormBanner(form,
          'Sei offline. La bozza è salvata localmente. Riprova quando sei connesso.',
          'draft'
        );
        return;
      }

      // Online: cancella la bozza (ottimistico; se il server restituisce un errore
      // la bozza è già persa — caso accettabile, il dato è nel form ancora visibile)
      await dbDelete(db, key);
      hideFormBanner(form);
    });
  }

  // ── Banner globale offline/online ────────────────────────────────────────

  const BANNER_ID = 'plancia-connectivity-banner';

  function updateConnectivityBanner() {
    let banner = document.getElementById(BANNER_ID);

    if (!navigator.onLine) {
      if (!banner) {
        banner = document.createElement('div');
        banner.id = BANNER_ID;
        banner.style.cssText = [
          'position:fixed', 'bottom:0', 'left:0', 'right:0', 'z-index:9999',
          'background:#dc3545', 'color:#fff', 'text-align:center',
          'padding:.5rem 1rem', 'font-size:.875rem', 'font-weight:500',
        ].join(';');
        banner.textContent = 'Sei offline — le modifiche vengono salvate localmente.';
        document.body.appendChild(banner);
      }
    } else {
      if (banner) {
        banner.style.background = '#198754';
        banner.textContent = 'Connessione ripristinata.';
        setTimeout(() => banner.remove(), 3000);
      }
    }
  }

  window.addEventListener('offline', updateConnectivityBanner);
  window.addEventListener('online',  updateConnectivityBanner);

  // ── Inizializzazione ─────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', async () => {
    updateConnectivityBanner();

    const forms = document.querySelectorAll('form[data-autosave-key]');
    if (!forms.length) return;

    let db;
    try {
      db = await openDB();
    } catch (err) {
      console.warn('plancia-autosave: IndexedDB non disponibile', err);
      return;
    }

    forms.forEach(form => wireForm(form, db));
  });
})();
