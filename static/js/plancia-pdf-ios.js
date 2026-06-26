/* Plancia — download PDF diario su PWA iOS standalone
 *
 * Su iOS, le PWA installate ("Aggiungi a Home") girano in una WebView priva della
 * toolbar di Safari. WebKit intercetta la navigazione verso un PDF con Quick Look,
 * che nella WebView standalone non ha pulsanti Share/"Apri in" (vedi CLAUDE.md § PDF diari).
 *
 * Soluzione (ispirata a Sergii Novikov, 2024):
 *   fetch(pdfUrl) → blob → URL.createObjectURL() → <a download> click
 * Un blob URL con attributo `download` viene trattato da iOS come un download, non
 * come navigazione: appare il foglio Share nativo con "Apri in Acrobat", "Salva su File",
 * ecc. Non richiede contesto user-gesture sincrono (a differenza di navigator.share).
 *
 * Fallback:
 *   1. navigator.share({ files }) — se il blob download non è disponibile
 *   2. window.location.href    — se il PDF non è ancora pronto o in caso di errore
 *
 * Attivo solo su PWA standalone (window.navigator.standalone o display-mode:standalone).
 * Su tutte le altre piattaforme lo script non interviene.
 */
(function () {
  'use strict';

  var isStandalone = window.navigator.standalone === true ||
    window.matchMedia('(display-mode: standalone)').matches;
  if (!isStandalone) return;

  document.addEventListener('click', function (event) {
    var link = event.target.closest('a[data-pdf-link]');
    if (!link) return;

    event.preventDefault();
    var href = link.href;

    link.classList.add('disabled');
    link.setAttribute('aria-disabled', 'true');

    fetch(href, { credentials: 'same-origin' })
      .then(function (response) {
        var contentType = response.headers.get('Content-Type') || '';
        if (!response.ok || contentType.indexOf('application/pdf') === -1) {
          // PDF non ancora pronto (task Celery in corso) o errore:
          // navighiamo normalmente, l'utente vede il messaggio sulla pagina.
          window.location.href = href;
          return null;
        }
        var nome = nomeFileDa(response, 'diario.pdf');
        return response.blob().then(function (blob) {
          scaricaBlob(blob, nome, href);
        });
      })
      .catch(function () {
        window.location.href = href;
      })
      .finally(function () {
        link.classList.remove('disabled');
        link.removeAttribute('aria-disabled');
      });
  });

  function nomeFileDa(response, fallback) {
    var header = response.headers.get('Content-Disposition') || '';
    var match = /filename[^;=\n]*=["']?([^"'\n;]+)["']?/.exec(header);
    return match ? match[1].trim() : fallback;
  }

  function scaricaBlob(blob, nome, fallbackHref) {
    // Tentativo 1: blob URL + <a download> — non richiede user-gesture sincrono,
    // su iOS mostra il foglio Share/Download nativo invece di Quick Look.
    try {
      var blobUrl = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = blobUrl;
      a.download = nome;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(blobUrl); }, 1000);
      return;
    } catch (e) {
      // createObjectURL non disponibile (raro) → tenta share
    }

    // Tentativo 2: Web Share API con file (iOS 15+)
    try {
      var file = new File([blob], nome, { type: 'application/pdf' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file] }).catch(function (err) {
          if (err && err.name !== 'AbortError') {
            window.location.href = fallbackHref;
          }
        });
        return;
      }
    } catch (e) {
      // navigator.share non disponibile
    }

    // Fallback finale: navigazione normale
    window.location.href = fallbackHref;
  }
})();
