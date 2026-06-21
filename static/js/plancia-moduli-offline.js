/* plancia-moduli-offline.js
 * Intercetta il submit dei form dei moduli CSQ (1–5), converte in PUT JSON
 * verso le API e accoda in IndexedDB quando la rete non è disponibile.
 *
 * Dipende da: plancia-idb.js (caricato prima in base.html)
 *
 * Attributi richiesti sul <form>:
 *   data-offline-modulo  = "anagrafica|presentazione|impresa_1|impresa_2|missione"
 *   data-offline-pk      = "<diario_pk>"
 *
 * Attributi aggiuntivi per la presentazione:
 *   data-prefix-membri   = "{{ formset.prefix }}"
 *
 * Attributi aggiuntivi per le imprese:
 *   data-prefix-posti        = "{{ posti_fs.prefix }}"
 *   data-prefix-specialita   = "{{ specialita_fs.prefix }}"
 *   data-prefix-brevetti     = "{{ brevetti_fs.prefix }}"
 */

(function () {
  'use strict';

  var API_CACHE_NAME = 'plancia-api-v2';

  // ---------------------------------------------------------------------------
  // Helpers generici
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
    // Rimuove classi di colore precedenti e applica quella nuova
    el.className = 'toast border-0 text-bg-' + (type || 'secondary');
    bootstrap.Toast.getOrCreateInstance(el, { delay: 6000 }).show();
  }

  function syncBadgeUpdate(n) {
    var badge   = document.getElementById('offline-sync-badge');
    var countEl = document.getElementById('offline-sync-count');
    if (!badge || !countEl) return;
    countEl.textContent = n;
    badge.classList.toggle('d-none', n === 0);
  }

  function setSubmitState(form, busy) {
    var btn = form.querySelector('[type="submit"]');
    if (!btn) return;
    btn.disabled    = busy;
    btn.textContent = busy ? 'Salvataggio…' : 'Salva';
  }

  // ---------------------------------------------------------------------------
  // Parser formset Django
  // Legge il management form (PREFIX-TOTAL_FORMS) e raccoglie le righe.
  // Righe con DELETE=checked o completamente vuote senza id vengono scartate.
  // ---------------------------------------------------------------------------

  function parseFormset(form, prefix, fields) {
    var totalEl = form.querySelector('[name="' + prefix + '-TOTAL_FORMS"]');
    if (!totalEl) return [];
    var total = parseInt(totalEl.value, 10);
    var items = [];

    for (var i = 0; i < total; i++) {
      var deleteEl = form.querySelector('[name="' + prefix + '-' + i + '-DELETE"]');
      if (deleteEl && deleteEl.checked) continue;

      var idEl = form.querySelector('[name="' + prefix + '-' + i + '-id"]');
      var item = { id: (idEl && idEl.value) ? parseInt(idEl.value, 10) : null };
      var allEmpty = true;

      for (var f = 0; f < fields.length; f++) {
        var key = fields[f];
        var el  = form.querySelector('[name="' + prefix + '-' + i + '-' + key + '"]');
        if (el) {
          item[key] = el.value || '';
          if (el.value && el.value.trim()) allEmpty = false;
        }
      }

      if (allEmpty && !item.id) continue;  // riga extra vuota
      items.push(item);
    }
    return items;
  }

  // ---------------------------------------------------------------------------
  // Estrattori per modulo
  // ---------------------------------------------------------------------------

  function extractAnagrafica(form) {
    var fd  = new FormData(form);
    var cbx = form.querySelector('[name="partecipa_evento"]');
    return {
      squadriglia_nome: fd.get('squadriglia_nome') || '',
      tipo_diario:      fd.get('tipo_diario')      || '',
      crp_nome:         fd.get('crp_nome')         || '',
      crp_cognome:      fd.get('crp_cognome')      || '',
      crp_email:        fd.get('crp_email')        || '',
      crp_cell:         fd.get('crp_cell')         || '',
      csq_nome:         fd.get('csq_nome')         || '',
      csq_cognome:      fd.get('csq_cognome')      || '',
      csq_email:        fd.get('csq_email')        || '',
      csq_cell:         fd.get('csq_cell')         || '',
      specialita:       fd.get('specialita')       || '',
      partecipa_evento: cbx ? cbx.checked : true,
    };
  }

  function extractPresentazione(form) {
    var fd     = new FormData(form);
    var prefix = form.dataset.prefixMembri || 'membrosq_set';
    return {
      cosa_sappiamo_fare: fd.get('cosa_sappiamo_fare') || '',
      membri: parseFormset(form, prefix, ['nome', 'ruolo', 'sentiero']),
    };
  }

  function extractImpresa(form) {
    var fd = new FormData(form);
    var pp = form.dataset.prefixPosti      || 'posti';
    var ps = form.dataset.prefixSpecialita || 'specialita';
    var pb = form.dataset.prefixBrevetti   || 'brevetti';
    return {
      titolo:       fd.get('titolo')       || '',
      data_inizio:  fd.get('data_inizio')  || null,
      data_fine:    fd.get('data_fine')    || null,
      perche:       fd.get('perche')       || '',
      come:         fd.get('come')         || '',
      cosa:         fd.get('cosa')         || '',
      link_esterno: fd.get('link_esterno') || '',
      posti_azione: parseFormset(form, pp, ['chi', 'cosa']),
      specialita:   parseFormset(form, ps, ['chi', 'nome', 'stato']),
      brevetti:     parseFormset(form, pb, ['chi', 'nome', 'stato']),
    };
  }

  function extractMissione(form) {
    var fd = new FormData(form);
    return {
      titolo:                  fd.get('titolo')                  || '',
      data:                    fd.get('data')                    || null,
      descrizione_svolgimento: fd.get('descrizione_svolgimento') || '',
    };
  }

  var EXTRACTORS = {
    anagrafica:    extractAnagrafica,
    presentazione: extractPresentazione,
    impresa_1:     extractImpresa,
    impresa_2:     extractImpresa,
    missione:      extractMissione,
  };

  // ---------------------------------------------------------------------------
  // URL API per modulo
  // ---------------------------------------------------------------------------

  function apiUrl(pk, modulo) {
    if (modulo === 'impresa_1') return '/api/diari/' + pk + '/modulo/impresa/1/';
    if (modulo === 'impresa_2') return '/api/diari/' + pk + '/modulo/impresa/2/';
    return '/api/diari/' + pk + '/modulo/' + modulo + '/';
  }

  // ---------------------------------------------------------------------------
  // Versione corrente: prova rete, poi cache SW, poi 0
  // ---------------------------------------------------------------------------

  async function getVersion(url) {
    try {
      var r = await fetch(url);
      if (r.ok) return (await r.json()).version;
    } catch (e) {
      if (window.caches) {
        try {
          var cached = await caches.match(url);
          if (cached) return (await cached.json()).version;
        } catch (e2) { /* ignore */ }
      }
    }
    return 0;
  }

  // Aggiorna la SW API_CACHE con i dati freschi restituiti dal PUT riuscito.
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
  // Submit handler
  // ---------------------------------------------------------------------------

  async function handleSubmit(event) {
    var form    = event.target;
    var modulo  = form.dataset.offlineModulo;
    var pk      = parseInt(form.dataset.offlinePk, 10);
    var extract = EXTRACTORS[modulo];

    // Non gestito: lascia passare il POST normale (graceful degradation)
    if (!modulo || !pk || !extract) return;

    event.preventDefault();
    setSubmitState(form, true);

    try {
      var url     = apiUrl(pk, modulo);
      var version = await getVersion(url);
      var data    = extract(form);
      var payload = { version: version, data: data };

      var resp = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify(payload),
      });

      if (resp.ok) {
        var result = await resp.json();
        await refreshApiCache(url, result);
        // Rimuovi eventuali item in coda per questo modulo (es. salvataggio dopo un conflitto)
        if (window.PlanciaIdb) {
          PlanciaIdb.getAll().then(function (items) {
            items.forEach(function (item) {
              if (item.diario_pk === pk && item.modulo === modulo) {
                PlanciaIdb.remove(item.id);
              }
            });
          }).catch(function () {});
        }
        showToast('Salvato', 'Le modifiche sono state salvate.', 'success');
        window.location.href = '/diari/' + pk + '/';
        return;
      }

      if (resp.status === 409) {
        var conflict = await resp.json();
        showToast(
          'Conflitto di versione',
          'I dati sono stati modificati da un altro dispositivo (v' +
            conflict.server_version + '). Ricarica la pagina prima di salvare.',
          'danger'
        );
        setSubmitState(form, false);
        return;
      }

      if (resp.status === 400) {
        var errBody = await resp.json();
        var msgs = [];
        var errs = errBody.errors || {};
        Object.keys(errs).forEach(function (k) {
          var v = errs[k];
          if (Array.isArray(v)) msgs = msgs.concat(v);
          else if (typeof v === 'string') msgs.push(v);
        });
        showToast('Dati non validi', msgs.join(' ') || 'Controlla i campi e riprova.', 'danger');
        setSubmitState(form, false);
        return;
      }

      if (resp.status === 401) {
        // Sessione scaduta: accoda il payload già pronto e mostra il banner.
        if (window.PlanciaIdb) {
          await PlanciaIdb.enqueue(pk, modulo, url, payload);
          if ('serviceWorker' in navigator && 'SyncManager' in window) {
            navigator.serviceWorker.ready
              .then(function (reg) { return reg.sync.register('plancia-sync'); })
              .catch(function () {});
          }
        }
        document.dispatchEvent(new CustomEvent('plancia:session-expired'));
        showToast(
          'Sessione scaduta',
          'Le modifiche sono state salvate localmente. Accedi di nuovo per sincronizzarle.',
          'warning'
        );
        setSubmitState(form, false);
        return;
      }

      showToast('Errore server', 'Errore ' + resp.status + '. Riprova tra poco.', 'warning');
      setSubmitState(form, false);

    } catch (networkErr) {
      // Rete non disponibile: accoda localmente
      if (!window.PlanciaIdb) {
        showToast('Errore', 'Salvataggio offline non disponibile.', 'danger');
        setSubmitState(form, false);
        return;
      }
      var queueUrl     = apiUrl(pk, modulo);
      var queueVersion = await getVersion(queueUrl).catch(function () { return 0; });
      var queueData    = EXTRACTORS[modulo](form);
      await PlanciaIdb.enqueue(pk, modulo, queueUrl, { version: queueVersion, data: queueData });

      // Registra Background Sync nel service worker (Chrome/Edge)
      if ('serviceWorker' in navigator && 'SyncManager' in window) {
        navigator.serviceWorker.ready.then(function (reg) {
          return reg.sync.register('plancia-sync');
        }).catch(function () { /* ignorato: il fallback è l'evento online */ });
      }

      showToast(
        'Salvato offline',
        'Sei offline. Le modifiche verranno sincronizzate automaticamente al ritorno della connessione.',
        'warning'
      );
      setSubmitState(form, false);
    }
  }

  // ---------------------------------------------------------------------------
  // Inizializzazione
  // ---------------------------------------------------------------------------

  document.addEventListener('DOMContentLoaded', function () {
    // Intercetta i form dei moduli
    document.querySelectorAll('form[data-offline-modulo]').forEach(function (form) {
      form.addEventListener('submit', handleSubmit);
    });

    // Badge pendenti: aggiornamento iniziale
    if (window.PlanciaIdb) {
      PlanciaIdb.count().then(syncBadgeUpdate).catch(function () {});
    }

    // Badge pendenti: aggiornamento su ogni cambio
    document.addEventListener('plancia:pending-count', function (e) {
      syncBadgeUpdate(e.detail);
    });
  });

})();
