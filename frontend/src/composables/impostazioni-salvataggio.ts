/**
 * Salvataggio di una sezione delle impostazioni: stato "in corso", errori per campo del
 * backend (422 `errori`) e avviso di esito. `esegui` non lancia: restituisce il risultato
 * o `null` se l'operazione è fallita.
 */
import { ref } from 'vue'

import { ErroreApi, type ErroriCampo } from '@/api/http'
import { useAvvisiStore } from '@/stores/avvisi'

export function useSalvataggio() {
  const avvisi = useAvvisiStore()
  const inCorso = ref(false)
  const errori = ref<ErroriCampo>({})

  async function esegui<T>(operazione: () => Promise<T>, messaggioOk?: string): Promise<T | null> {
    inCorso.value = true
    errori.value = {}
    try {
      const r = await operazione()
      if (messaggioOk) avvisi.mostra(messaggioOk)
      return r
    } catch (e) {
      if (e instanceof ErroreApi) {
        errori.value = e.errori
        avvisi.mostra(e.message, 'danger', 8000)
      } else {
        avvisi.mostra(e instanceof Error ? e.message : 'Errore imprevisto.', 'danger', 8000)
      }
      return null
    } finally {
      inCorso.value = false
    }
  }

  return { inCorso, errori, esegui }
}
