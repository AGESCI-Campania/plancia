/// <reference types="vite-plugin-pwa/vue" />
/**
 * Aggiornamento della PWA. Il service worker è in modalità "prompt": la versione nuova si
 * installa solo quando l'utente accetta, così nessuno perde un modulo a metà compilazione.
 *
 * Due segnali di "c'è una versione nuova":
 * - il browser ha già scaricato un service worker nuovo (`needRefresh`);
 * - il server dichiara una versione più recente di quella installata (`versioneInferiore`),
 *   anche quando il browser non ha ancora controllato: `aggiornaOra` lo forza a farlo.
 */
import { useRegisterSW } from 'virtual:pwa-register/vue'
import { watch } from 'vue'

const ATTESA_MS = 30_000

let registrazione: ServiceWorkerRegistration | undefined

export const { needRefresh, updateServiceWorker } = useRegisterSW({
  immediate: true,
  onRegisteredSW(_url, trovata) {
    registrazione = trovata
  },
})

/** `locale` è precedente a `server`? Entrambe X.Y.Z; altri formati non sono motivo di aggiornare. */
export function versioneInferiore(locale: string, server: string): boolean {
  const FORMA = /^\d+\.\d+\.\d+$/
  if (!FORMA.test(locale) || !FORMA.test(server)) return false
  const a = locale.split('.').map(Number)
  const b = server.split('.').map(Number)
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i]! < b[i]!
  }
  return false
}

/** Finché la nuova versione è installata, o scade il tempo. */
function attendiNuovaVersione(): Promise<void> {
  return new Promise((risolvi) => {
    const fine = () => {
      clearTimeout(limite)
      smetti()
      risolvi()
    }
    const limite = setTimeout(fine, ATTESA_MS)
    const smetti = watch(needRefresh, (pronta) => {
      if (pronta) fine()
    })
  })
}

/** Il pulsante Aggiorna: chiede subito al browser la versione nuova e ricarica l'app. */
export async function aggiornaOra(): Promise<void> {
  let pronta = needRefresh.value || !!registrazione?.waiting
  if (!pronta && registrazione) {
    const attesa = attendiNuovaVersione()
    try {
      await registrazione.update()
      await attesa
    } catch {
      // Niente rete o nessuna risposta: il ricaricamento qui sotto resta la cosa migliore.
    }
    pronta = needRefresh.value || !!registrazione.waiting
  }
  if (pronta) await updateServiceWorker(true)
  else window.location.reload()
}
