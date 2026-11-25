// Avviso nei browser troppo vecchi per Bootstrap 6 e per la SPA (da browser-check.js del tema
// AGESCI Campania 3.0.0a5). Script classico ed ES5, fuori dal bundle: deve girare proprio dove
// l'app non parte. Controlla le funzionalità, non la versione: Safari/iOS 18 non vede l'avviso.
(function () {
  'use strict'

  var CHIAVE = 'plancia:avviso-browser-chiuso'
  var TESTO =
    'Questo browser è troppo vecchio: Plancia potrebbe non aprirsi o non funzionare bene. ' +
    'Aggiorna il browser o il dispositivo (su iPhone e iPad serve iOS 18 o successivo).'

  function supporta(proprieta, valore) {
    return !!(window.CSS && CSS.supports && CSS.supports(proprieta, valore))
  }

  function compatibile() {
    return (
      supporta('color', 'light-dark(red, blue)') &&
      supporta('color', 'oklch(50% 0.1 20)') &&
      supporta('color', 'color-mix(in oklch, red, blue)') &&
      supporta('container-type', 'inline-size') &&
      CSS.supports('selector(:has(a))') &&
      'CSSLayerBlockRule' in window &&
      'HTMLDialogElement' in window &&
      'noModule' in document.createElement('script')
    )
  }

  function mostra() {
    // Senza @layer il layout a viewport fisso renderebbe irraggiungibile il contenuto
    document.body.style.height = 'auto'
    document.body.style.overflow = 'auto'

    try {
      if (sessionStorage.getItem(CHIAVE)) return
    // eslint-disable-next-line @typescript-eslint/no-unused-vars -- ES5: il parametro è obbligatorio
    } catch (e) {
      // storage bloccato: l'avviso si mostra comunque
    }

    var avviso = document.createElement('div')
    avviso.id = 'avviso-browser'
    avviso.setAttribute('role', 'alert')
    // Stili qui e non nel CSS: non devono dipendere da Bootstrap
    avviso.style.cssText =
      'display:flex;align-items:center;padding:12px 16px;background:#fff3cd;color:#332701;' +
      'border-bottom:1px solid #997404;font:16px/1.4 sans-serif'
    var testo = document.createElement('span')
    testo.style.cssText = 'flex:1'
    testo.textContent = TESTO
    var chiudi = document.createElement('button')
    chiudi.type = 'button'
    chiudi.textContent = 'Chiudi'
    chiudi.style.cssText =
      'margin-left:16px;padding:6px 12px;background:#332701;color:#fff;border:0;font:inherit;cursor:pointer'
    chiudi.onclick = function () {
      avviso.parentNode.removeChild(avviso)
      try {
        sessionStorage.setItem(CHIAVE, '1')
      // eslint-disable-next-line @typescript-eslint/no-unused-vars -- ES5: il parametro è obbligatorio
      } catch (e) {
        // storage bloccato
      }
    }
    avviso.appendChild(testo)
    avviso.appendChild(chiudi)
    document.body.insertBefore(avviso, document.body.firstChild)
  }

  if (!compatibile()) mostra()
})()
