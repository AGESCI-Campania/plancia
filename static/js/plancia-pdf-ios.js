/* Plancia — download PDF diario su PWA iOS standalone
 *
 * Problema: su iOS standalone (PWA installata), qualsiasi navigazione verso un PDF —
 * URL diretto, blob URL, redirect — viene intercettata da WebKit con Quick Look.
 * In modalità standalone Quick Look non ha toolbar, né Share, né "Apri in" Acrobat.
 *
 * L'unica via d'uscita è navigator.share({ files }), che mostra il foglio Share nativo
 * (incluso "Apri in Acrobat Reader", "Salva su File" ecc.). Il vincolo di iOS è che
 * navigator.share DEVE essere chiamato all'interno di una user gesture. Dopo un fetch()
 * asincrono il contesto gesture è scaduto → NotAllowedError.
 *
 * Soluzione a due tap:
 *   1° tap → avvia fetch, scarica il PDF in background, salva il File in cache.
 *             Il bottone diventa verde ("Apri PDF") quando il download è pronto.
 *   2° tap → questo è una nuova user gesture → navigator.share({ files }) funziona.
 *
 * Se navigator.share non è disponibile (iOS < 15), fallback a window.location.href
 * (apre Quick Look — peggiore ma senza alternative su iOS datato).
 */
(function () {
  'use strict';

  var isStandalone = window.navigator.standalone === true ||
    window.matchMedia('(display-mode: standalone)').matches;
  if (!isStandalone) return;

  // WeakMap: link element → undefined | 'loading' | File
  var cache = new WeakMap();

  document.addEventListener('click', function (e) {
    var link = e.target.closest('a[data-pdf-link]');
    if (!link) return;

    var stato = cache.get(link);

    if (stato instanceof File) {
      // 2° tap — file già pronto, questa è una user gesture fresca
      e.preventDefault();
      condividi(link, stato);
      return;
    }

    if (stato === 'loading') {
      // Fetch in corso — ignora il tap
      e.preventDefault();
      return;
    }

    // 1° tap — avvia il download in background
    e.preventDefault();
    cache.set(link, 'loading');
    avviaFetch(link);
  });

  function avviaFetch(link) {
    link.classList.add('disabled');
    link.setAttribute('aria-disabled', 'true');

    fetch(link.href, { credentials: 'same-origin' })
      .then(function (response) {
        var ct = response.headers.get('Content-Type') || '';
        if (!response.ok || ct.indexOf('application/pdf') === -1) {
          // PDF non ancora pronto (task in coda): naviga normalmente,
          // l'utente vedrà il messaggio sulla pagina del diario.
          cache.delete(link);
          window.location.href = link.href;
          return null;
        }
        var nome = nomeFileDa(response, 'diario.pdf');
        return response.blob().then(function (blob) {
          return new File([blob], nome, { type: 'application/pdf' });
        });
      })
      .then(function (file) {
        if (!file) return; // già navigato (caso non-PDF)
        cache.set(link, file);
        // PDF pronto: rendi il bottone cliccabile e cambia colore
        link.classList.remove('disabled', 'btn-outline-secondary');
        link.removeAttribute('aria-disabled');
        link.classList.add('btn-success');
      })
      .catch(function () {
        cache.delete(link);
        link.classList.remove('disabled');
        link.removeAttribute('aria-disabled');
        window.location.href = link.href;
      });
  }

  function nomeFileDa(response, fallback) {
    var header = response.headers.get('Content-Disposition') || '';
    var match = /filename[^;=\n]*=["']?([^"'\n;]+)["']?/.exec(header);
    return match ? match[1].trim() : fallback;
  }

  function condividi(link, file) {
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      navigator.share({ files: [file] }).catch(function (err) {
        // AbortError: l'utente ha chiuso il foglio → nessuna azione
        if (err && err.name !== 'AbortError') {
          window.location.href = link.href;
        }
      });
    } else {
      // Fallback: iOS < 15 senza supporto file-sharing — apre Quick Lock
      window.location.href = link.href;
    }
  }
})();
