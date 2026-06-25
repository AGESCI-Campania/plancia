/* Plancia — apertura PDF diario su PWA iOS standalone
 *
 * Su iOS, le PWA installate ("Aggiungi a Home") girano in una WebView priva della
 * toolbar di Safari. WebKit intercetta la navigazione verso un PDF con la sua
 * anteprima Quick Look indipendentemente da target="_blank": l'anteprima resta
 * senza alcun pulsante per uscire o condividere il file, anche dopo il fix lato
 * link (vedi CLAUDE.md § PDF diari).
 *
 * Per questi dispositivi intercettiamo il click sui link al PDF e usiamo la Web
 * Share API per mostrare il foglio di condivisione nativo di iOS (Annulla, Salva
 * su File, Condividi, Stampa...). Su tutte le altre piattaforme il link resta
 * invariato: target="_blank" + Content-Disposition: attachment funzionano già.
 */
(function () {
  'use strict';

  var isIosStandalone = window.navigator.standalone === true;
  if (!isIosStandalone || !navigator.canShare) return;

  document.querySelectorAll('a[data-pdf-link]').forEach(function (link) {
    link.addEventListener('click', function (event) {
      event.preventDefault();
      apriPdfCondiviso(link);
    });
  });

  function nomeFileDa(response, fallback) {
    var header = response.headers.get('Content-Disposition') || '';
    var match = /filename="?([^"]+)"?/.exec(header);
    return match ? match[1] : fallback;
  }

  function apriPdfCondiviso(link) {
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
