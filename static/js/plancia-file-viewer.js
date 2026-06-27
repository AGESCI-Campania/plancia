/* Plancia — viewer inline per PDF, CSV e XLSX su PWA standalone
 *
 * Problema: su iOS PWA standalone qualsiasi navigazione verso un PDF viene
 * intercettata da Quick Look senza toolbar né Share. Su Android alcuni dispositivi
 * non rispettano Content-Disposition: attachment per i file binari.
 *
 * Soluzione: pagina viewer dedicata che effettua il fetch del file in background
 * al caricamento della pagina. Quando il file è pronto il pulsante "Scarica"
 * si attiva. Su iOS PWA usa navigator.share({ files }); su tutti gli altri usa
 * <a download> con blob URL.
 *
 * Il viewer mostra l'anteprima inline (iframe) solo per i PDF su non-iOS; per
 * tutti gli altri formati (CSV, XLSX) mostra un placeholder con il pulsante.
 */
(function () {
  'use strict';

  var wrap = document.getElementById('file-viewer-wrap');
  if (!wrap) return;

  var fileUrl = wrap.dataset.fileUrl;
  var filename = wrap.dataset.fileFilename;
  var mime = wrap.dataset.fileMime;

  var frame = document.getElementById('viewer-frame');
  var loadingEl = document.getElementById('viewer-loading');
  var placeholderEl = document.getElementById('viewer-placeholder');
  var errEl = document.getElementById('viewer-error');
  var dlBtn = document.getElementById('viewer-download-btn');

  var isIosPwa = window.navigator.standalone === true ||
    (window.matchMedia('(display-mode: standalone)').matches &&
      /iPad|iPhone|iPod/.test(navigator.userAgent));
  var isPdf = mime === 'application/pdf';

  var cachedFile = null;

  function showError() {
    loadingEl.style.display = 'none';
    errEl.style.display = 'block';
  }

  function blobDownload(file) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(file);
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { document.body.removeChild(a); }, 100);
  }

  function activateButton(file) {
    cachedFile = file;
    dlBtn.disabled = false;
    dlBtn.classList.remove('btn-secondary');
    dlBtn.classList.add('btn-primary');
  }

  fetch(fileUrl, { credentials: 'same-origin' })
    .then(function (r) {
      var ct = r.headers.get('Content-Type') || '';

      // Se il PDF non è ancora disponibile (il backend reindirizza alla pagina
      // del diario con un messaggio), naviga normalmente invece di mostrare errore.
      if (isPdf && r.ok && !ct.startsWith('application/pdf')) {
        window.location.href = fileUrl;
        return null;
      }

      if (!r.ok) throw new Error('http-error');

      var inferredMime = ct.split(';')[0].trim() || mime;
      return r.blob().then(function (blob) {
        return new File([blob], filename, { type: inferredMime });
      });
    })
    .then(function (file) {
      if (!file) return; // già navigato (PDF non pronto)

      loadingEl.style.display = 'none';
      activateButton(file);

      if (isPdf && !isIosPwa && frame) {
        // Desktop e Android: mostra anteprima inline
        frame.src = URL.createObjectURL(file);
        frame.style.display = 'block';
      } else {
        // iOS PWA (Quick Lock) oppure formato non-PDF: solo placeholder
        placeholderEl.style.display = 'block';
      }
    })
    .catch(showError);

  dlBtn.addEventListener('click', function () {
    if (!cachedFile) return;
    if (navigator.canShare && navigator.canShare({ files: [cachedFile] })) {
      navigator.share({ files: [cachedFile], title: filename }).catch(function (err) {
        if (err && err.name !== 'AbortError') blobDownload(cachedFile);
      });
    } else {
      blobDownload(cachedFile);
    }
  });
})();
