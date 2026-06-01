/* Plancia — widget upload foto con supporto offline.
 *
 * Attivato da qualsiasi elemento con:
 *   data-foto-base-url="..."   URL base allegati del diario (es. /diari/42/allegati/)
 *   data-foto-modulo="..."     "impresa_1" | "impresa_2" | "missione"
 *   data-foto-can-edit="1"     presente solo se l'utente può modificare
 *
 * Flusso online:  selezione → AJAX upload → JSON response → card in gallery.
 * Flusso offline: selezione → IndexedDB   → card "In attesa"
 *                 tornando online          → flush automatico da IndexedDB.
 *
 * DB separato da plancia-autosave per evitare accoppiamento di versioni.
 */
(function () {
  'use strict';

  const DB_NAME    = 'plancia-photos';
  const DB_VERSION = 1;
  const STORE      = 'pending';
  const MAX_BYTES  = 20 * 1024 * 1024; // 20 MB
  const ACCEPT     = 'image/jpeg,image/png,image/webp,image/heic,image/heif';

  // ── IndexedDB helpers ────────────────────────────────────────────────────

  let _db = null;

  function openDB() {
    if (_db) return Promise.resolve(_db);
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = e => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: 'localId' });
        }
      };
      req.onsuccess = e => { _db = e.target.result; resolve(_db); };
      req.onerror   = e => reject(e.target.error);
    });
  }

  function dbGetAll(db) {
    return new Promise((resolve, reject) => {
      const req = db.transaction(STORE, 'readonly').objectStore(STORE).getAll();
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

  function dbDelete(db, localId) {
    return new Promise((resolve, reject) => {
      const req = db.transaction(STORE, 'readwrite').objectStore(STORE).delete(localId);
      req.onsuccess = () => resolve();
      req.onerror   = e => reject(e.target.error);
    });
  }

  // ── CSRF ─────────────────────────────────────────────────────────────────

  function getCsrf() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  // ── Formatters ───────────────────────────────────────────────────────────

  function fmtBytes(n) {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }

  const BADGE = {
    locale:   ['bg-secondary', 'Locale'],
    in_coda:  ['bg-warning text-dark', 'In coda'],
    caricato: ['bg-success', 'Drive'],
    pending:  ['bg-info text-dark', 'In attesa'],
  };

  // ── Card rendering ───────────────────────────────────────────────────────

  function makeThumbnailUrl(entry) {
    // entry.url è valorizzato per allegati già caricati
    // entry.blob è valorizzato per pending locali
    if (entry.url) return entry.url;
    if (entry.blob && entry.blob.type && entry.blob.type.startsWith('image/')) {
      return URL.createObjectURL(entry.blob);
    }
    return null;
  }

  function buildCard(entry, canEdit, onDelete) {
    const [badgeCls, badgeLbl] = BADGE[entry.stato_sync || 'pending'] || BADGE.pending;
    const thumb = makeThumbnailUrl(entry);
    const isRevocable = canEdit && (entry.stato_sync !== 'caricato' || entry.localId);

    const col = document.createElement('div');
    col.className = 'col-6 col-sm-4 col-md-3 col-xl-2';
    col.dataset.cardId = entry.id || entry.localId;

    col.innerHTML = `
      <div class="card h-100 shadow-sm">
        ${thumb
          ? `<img src="${thumb}" class="card-img-top" style="height:90px;object-fit:cover;" alt="">`
          : `<div class="card-img-top d-flex align-items-center justify-content-center bg-light"
               style="height:90px;font-size:2rem;color:#adb5bd;">📎</div>`}
        <div class="card-body p-2">
          <p class="card-text small text-truncate mb-1" title="${escHtml(entry.nome)}">${escHtml(entry.nome)}</p>
          <div class="d-flex align-items-center gap-1 flex-wrap">
            <span class="badge ${badgeCls}" style="font-size:.65rem;">${badgeLbl}</span>
            <span class="text-muted" style="font-size:.65rem;">${fmtBytes(entry.dimensione || 0)}</span>
          </div>
        </div>
        ${isRevocable ? `
        <div class="card-footer p-1 text-end border-0 bg-transparent">
          <button type="button" class="btn btn-link btn-sm text-danger p-0 foto-delete-btn"
                  data-id="${entry.id || ''}"
                  data-local-id="${entry.localId || ''}">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
              <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/>
              <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/>
            </svg>
          </button>
        </div>` : ''}
      </div>`;

    col.querySelector('.foto-delete-btn')?.addEventListener('click', () => onDelete(entry));
    return col;
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Widget per singolo container ─────────────────────────────────────────

  async function initWidget(container, db) {
    const baseUrl  = container.dataset.fotoBaseUrl;   // es. /diari/42/allegati/
    const modulo   = container.dataset.fotoModulo;
    const canEdit  = container.hasAttribute('data-foto-can-edit');
    const uploadUrl = `${baseUrl}upload/`;

    // --- Rendering ---
    container.innerHTML = `
      <h5 class="border-bottom pb-1 mb-3">
        Foto
        <small class="text-muted fw-normal" style="font-size:.75rem;"></small>
      </h5>
      <div class="foto-gallery row g-2 mb-3"></div>
      ${canEdit ? `
      <label class="btn btn-outline-secondary btn-sm foto-add-label">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor"
             class="me-1" viewBox="0 0 16 16">
          <path d="M15 12a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h1.172a3 3 0 0 0 2.12-.879l.83-.828A1 1 0 0 1 6.827 3h2.344a1 1 0 0 1 .707.293l.828.828A3 3 0 0 0 12.828 5H14a1 1 0 0 1 1 1zM2 4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-1.172a2 2 0 0 1-1.414-.586l-.828-.828A2 2 0 0 0 9.172 2H6.828a2 2 0 0 0-1.414.586l-.828.828A2 2 0 0 1 3.172 4z"/>
          <path d="M8 11a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5m0 1a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7M3 6.5a.5.5 0 1 1-1 0 .5.5 0 0 1 1 0"/>
        </svg>
        Aggiungi foto
        <input type="file" accept="${ACCEPT}" multiple hidden class="foto-file-input">
      </label>
      <small class="text-muted ms-2 d-inline-block mt-1" style="font-size:.75rem;">
        JPEG, PNG, WebP, HEIC — max 20 MB cad.
      </small>` : ''}
    `;

    const gallery   = container.querySelector('.foto-gallery');
    const fileInput = container.querySelector('.foto-file-input');
    const subtitle  = container.querySelector('h5 small');

    // Stato condiviso: localId → card col element
    const cards = new Map();

    function updateSubtitle() {
      subtitle.textContent = cards.size ? `(${cards.size})` : '';
    }

    // --- Cancellazione ---
    async function deleteEntry(entry) {
      const cardId = entry.id || entry.localId;
      if (!confirm(`Eliminare "${entry.nome}"?`)) return;

      if (entry.localId) {
        // Solo locale (IndexedDB)
        await dbDelete(db, entry.localId);
      } else {
        // Già sul server
        const resp = await fetch(`${baseUrl}${entry.id}/elimina/`, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrf() },
        });
        if (!resp.ok) { alert('Errore durante l\'eliminazione.'); return; }
      }
      cards.get(cardId)?.remove();
      cards.delete(cardId);
      updateSubtitle();
    }

    // --- Aggiunge card ---
    function addCard(entry) {
      const cardId = entry.id || entry.localId;
      if (cards.has(cardId)) return;
      const col = buildCard(entry, canEdit, deleteEntry);
      gallery.appendChild(col);
      cards.set(cardId, col);
      updateSubtitle();
    }

    // --- Upload singolo file (AJAX) ---
    async function uploadFile(file) {
      const localId = `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`;

      // Mostra subito come "In attesa" durante l'upload
      const preview = { localId, nome: file.name, dimensione: file.size, stato_sync: 'pending',
                         blob: file, url: null };
      addCard(preview);

      const fd = new FormData();
      fd.append('modulo', modulo);
      fd.append('file', file);

      try {
        const resp = await fetch(uploadUrl, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrf() },
          body: fd,
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.error || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        // Sostituisce la card temporanea con quella del server
        cards.get(localId)?.remove();
        cards.delete(localId);
        addCard(data);
      } catch (err) {
        if (!navigator.onLine) {
          // Offline: salva in IndexedDB, lascia la card "In attesa"
          await dbPut(db, {
            localId, diaroPk: parseInt(baseUrl.split('/').filter(Boolean).slice(-2)[0], 10),
            modulo, nome: file.name, mime: file.type,
            dimensione: file.size, blob: file, ts: Date.now(),
          });
        } else {
          console.error('plancia-foto upload error:', err);
          cards.get(localId)?.remove();
          cards.delete(localId);
          alert(`Errore upload "${file.name}": ${err.message}`);
        }
      }
    }

    // --- Flush coda offline ---
    async function flushPending() {
      if (!navigator.onLine) return;
      const all = await dbGetAll(db);
      const mine = all.filter(e => e.modulo === modulo);
      for (const entry of mine) {
        const file = new File([entry.blob], entry.nome, { type: entry.mime });
        const fd = new FormData();
        fd.append('modulo', modulo);
        fd.append('file', file);
        try {
          const resp = await fetch(uploadUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrf() },
            body: fd,
          });
          if (!resp.ok) continue;
          const data = await resp.json();
          await dbDelete(db, entry.localId);
          // Aggiorna la card esistente se presente, altrimenti aggiunge
          if (cards.has(entry.localId)) {
            cards.get(entry.localId).remove();
            cards.delete(entry.localId);
          }
          addCard(data);
        } catch (_) {
          // Riproverà alla prossima connessione
        }
      }
    }

    // --- Carica allegati esistenti dal server ---
    try {
      const resp = await fetch(`${baseUrl}?modulo=${encodeURIComponent(modulo)}`);
      if (resp.ok) {
        const data = await resp.json();
        data.results.forEach(addCard);
      }
    } catch (_) { /* offline, ignora */ }

    // --- Carica pending da IndexedDB ---
    const pending = await dbGetAll(db);
    pending.filter(e => e.modulo === modulo).forEach(e => addCard({ ...e, stato_sync: 'pending' }));

    // --- Ascoltatori ---
    if (fileInput) {
      fileInput.addEventListener('change', async () => {
        const files = [...fileInput.files];
        fileInput.value = '';
        for (const f of files) {
          if (f.size > MAX_BYTES) { alert(`"${f.name}" supera il limite di 20 MB.`); continue; }
          await uploadFile(f);
        }
      });
    }

    window.addEventListener('online', flushPending);

    // Auto-flush se siamo già online all'avvio (pending dal giro precedente)
    if (navigator.onLine) flushPending();
  }

  // ── Bootstrap: trova tutti i widget nella pagina ─────────────────────────

  document.addEventListener('DOMContentLoaded', async () => {
    const widgets = document.querySelectorAll('[data-foto-base-url]');
    if (!widgets.length) return;

    let db;
    try {
      db = await openDB();
    } catch (err) {
      console.warn('plancia-foto: IndexedDB non disponibile', err);
      return;
    }

    widgets.forEach(w => initWidget(w, db));
  });
})();
