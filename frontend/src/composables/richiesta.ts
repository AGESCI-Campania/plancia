/**
 * Stato di una richiesta all'API per le pagine: dati, caricamento, errore (messaggio ed
 * errori per campo), con `esegui` che non lancia (l'errore finisce in `errore`).
 */
import { ref, shallowRef, type Ref, type ShallowRef } from 'vue'

import { ErroreApi, type ErroriCampo } from '@/api/http'

export interface Richiesta<T> {
  dati: ShallowRef<T | null>
  inCorso: Ref<boolean>
  errore: Ref<string>
  erroriCampo: Ref<ErroriCampo>
  /** Stato HTTP dell'ultimo errore (0 = offline). */
  stato: Ref<number | null>
  esegui: () => Promise<T | null>
}

export function useRichiesta<T>(operazione: () => Promise<T>): Richiesta<T> {
  const dati = shallowRef<T | null>(null)
  const inCorso = ref(false)
  const errore = ref('')
  const erroriCampo = ref<ErroriCampo>({})
  const stato = ref<number | null>(null)

  async function esegui(): Promise<T | null> {
    inCorso.value = true
    errore.value = ''
    erroriCampo.value = {}
    stato.value = null
    try {
      dati.value = await operazione()
      return dati.value
    } catch (e) {
      if (e instanceof ErroreApi) {
        errore.value = e.message
        erroriCampo.value = e.errori
        stato.value = e.stato
      } else {
        errore.value = e instanceof Error ? e.message : 'Errore imprevisto.'
      }
      return null
    } finally {
      inCorso.value = false
    }
  }

  return { dati, inCorso, errore, erroriCampo, stato, esegui }
}
