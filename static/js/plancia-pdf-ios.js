/* Plancia — apertura PDF diario su PWA iOS standalone
 *
 * Su iOS, le PWA installate ("Aggiungi a Home") girano in una WebView priva della
 * toolbar di Safari. WebKit intercetta la navigazione verso un PDF con la sua
 * anteprima Quick Look anche con target="_blank": l'anteprima resta senza alcun
 * pulsante per uscire o condividere il file, e senza l'opzione "Apri in" per le app
 * di lettura PDF installate (Acrobat ecc.), perché quella richiede la toolbar di
 * Safari che la WebView standalone non ha (vedi CLAUDE.md § PDF diari).
 *
 * Fix in due tentativi:
 * 1. Apriamo la pagina "launcher" (`data-pdf-apri-url`, HTML non previewable) in una
 *    nuova finestra: una pagina HTML, a differenza del PDF, viene delegata dal
 *    sistema al browser Safari vero e proprio. Una volta lì, il redirect lato
 *    client della pagina apre il PDF dentro Safari, con la toolbar nativa completa
 *    (incluso "Apri in" Acrobat e altri lettori PDF).
 * 2. Se la finestra non si apre (popup bloccato), fallback al download via fetch +
 *    Web Share API: foglio di condivisione nativo (Annulla, Salva su File,
 *    Condividi, Stampa) — non mostra "Apri in" ma almeno non blocca l'utente.
 *
 * Su tutte le altre piattaforme lo script non interviene: il link normale
 * (target="_blank" + Content-Disposition: attachment) funziona già.
 */
(function () {
  'use strict';

  var isIosStandalone = window.navigator.standalone === true;
  if (!isIosStandalone) return;

  document.querySelectorAll('a[data-pdf-link]').forEach(function (link) {
    link.addEventListener('click', function (event) {
      event.preventDefault();
      var apriUrl = link.getAttribute('data-pdf-apri-url');
      var win = apriUrl ? window.open(apriUrl, '_blank') : null;
      if (!win && navigator.canShare) {
        condividiPdf(link);
      }
    });
  });

  function nomeFileDa(response, fallback) {
    var header = response.headers.get('Content-Disposition') || '';
    var match = /filename="?([^"]+)"?/.exec(header);
    return match ? match[1] : fallback;
  }

  function condividiPdf(link) {
    var href = link.href;
    link.classList.add('disabled');
    link.setAttribute('aria-disabled', 'true');

    fetch(href, { credentials: 'same-origin' })
      .then(function (response) {
        var contentType = response.headers.get('Content-Type') || '';
        if (!response.ok || contentType.indexOf('application/pdf') === -1) {
          // PDF non ancora pronto (rigenerazione in corso) o redirect d'errore:
          // navighiamo normalmente, l'utente vedrà il messaggio sulla pagina di dettaglio.
          window.location.href = href;
          return null;
        }
        return response.blob().then(function (blob) {
          var nome = nomeFileDa(response, 'diario.pdf');
          var file = new File([blob], nome, { type: 'application/pdf' });
          if (navigator.canShare({ files: [file] })) {
            return navigator.share({ files: [file] });
          }
          window.location.href = href;
          return null;
        });
      })
      .catch(function (err) {
        // AbortError: l'utente ha chiuso il foglio di condivisione, non è un errore reale.
        if (err && err.name !== 'AbortError') {
          window.location.href = href;
        }
      })
      .finally(function () {
        link.classList.remove('disabled');
        link.removeAttribute('aria-disabled');
      });
  }
})();
