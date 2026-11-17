/**
 * Dati comuni alle pagine dei moduli: il diario (intestazione, stato, permessi calcolati dal
 * backend, completezza dei moduli) e le scelte dei campi (`/diari/moduli/opzioni`, in cache
 * per tutta la sessione della pagina).
 */
import { ref, shallowRef } from 'vue'

import { api } from '@/api/http'
import { leggiConCopia } from '@/offline/letture'
import type { components } from '@/api/schema'

export type DiarioDettaglio = components['schemas']['DiarioDettaglioSchema']
export type OpzioniModuli = components['schemas']['OpzioniModuliDiarioSchema']
export type Allegato = components['schemas']['AllegatoSchema']
export type Scelta = components['schemas']['SceltaSchema']

let opzioniInCache: Promise<OpzioniModuli> | null = null

/** Scelte dei campi dei moduli (una sola richiesta per sessione). */
export function caricaOpzioniModuli(): Promise<OpzioniModuli> {
  opzioniInCache ??= leggiConCopia('/diari/moduli/opzioni', () => api.get<OpzioniModuli>('/diari/moduli/opzioni'))
    .then((r) => r.dati)
    .catch((e: unknown) => {
    opzioniInCache = null
    throw e
  })
  return opzioniInCache
}

/** Solo per i test. */
export function svuotaCacheOpzioni(): void {
  opzioniInCache = null
}

export function useDiarioCompilazione(diarioId: number | string) {
  const diario = shallowRef<DiarioDettaglio | null>(null)
  const opzioni = shallowRef<OpzioniModuli | null>(null)
  const errore = ref('')
  const inCorso = ref(false)
  /** Dati presi dalla copia sul dispositivo (offline): possono non essere aggiornati. */
  const copiaLocale = ref(false)
  const leggiDiario = () => leggiConCopia(`/diari/${diarioId}`, () => api.get<DiarioDettaglio>(`/diari/${diarioId}`))

  async function carica(): Promise<void> {
    inCorso.value = true
    errore.value = ''
    try {
      const [d, o] = await Promise.all([leggiDiario(), caricaOpzioniModuli()])
      diario.value = d.dati
      copiaLocale.value = d.copia
      opzioni.value = o
    } catch (e) {
      errore.value = e instanceof Error ? e.message : 'Errore imprevisto.'
    } finally {
      inCorso.value = false
    }
  }

  /** Dopo un salvataggio: aggiorna stato e completezza (in silenzio, senza spinner). */
  async function aggiorna(): Promise<void> {
    try {
      const d = await leggiDiario()
      diario.value = d.dati
      copiaLocale.value = d.copia
    } catch {
      // L'intestazione resta quella di prima: il modulo è comunque salvato.
    }
  }

  return { diario, opzioni, errore, inCorso, copiaLocale, carica, aggiorna }
}
