/**
 * Riautenticazione per le operazioni sensibili (MFA, passkey, aggiornamento del server…).
 * allauth risponde 401 con il flusso `reauthenticate`/`mfa_reauthenticate`; le API di Plancia
 * 401 con `riautenticazione_richiesta: true`. In entrambi i casi la SPA chiede password o
 * codice nella finestra di `RiautenticazioneDialogo.vue` e ripete l'operazione.
 */
import { ref } from 'vue'

import { allauth, type RispostaAllauth } from '@/api/allauth'
import { ErroreApi } from '@/api/http'

/** Richiesta in corso, letta dalla finestra (montata una sola volta in App.vue). */
export const richiestaRiautenticazione = ref<{
  conCodice: boolean
  risolvi: (ok: boolean) => void
} | null>(null)

function chiedi(conCodice: boolean): Promise<boolean> {
  return new Promise((risolvi) => {
    richiestaRiautenticazione.value = { conCodice, risolvi }
  })
}

export async function confermaRiautenticazione(segreto: string, conCodice: boolean): Promise<string> {
  const r = conCodice ? await allauth.mfaRiautentica(segreto) : await allauth.riautentica(segreto)
  return r.status === 200 ? '' : (r.errors?.[0]?.message ?? 'Verifica non riuscita.')
}

function richiedeRiautenticazione(r: RispostaAllauth): 'password' | 'codice' | null {
  if (r.status !== 401) return null
  const flussi = r.data?.flows?.map((f) => f.id) ?? []
  if (flussi.includes('reauthenticate')) return 'password'
  if (flussi.includes('mfa_reauthenticate')) return 'codice'
  return null
}

/** Esegue un'operazione di allauth; se serve, riautentica e la ripete una volta. */
export async function conRiautenticazioneAllauth<T>(
  operazione: () => Promise<RispostaAllauth<T>>,
): Promise<RispostaAllauth<T>> {
  const r = await operazione()
  const tipo = richiedeRiautenticazione(r)
  if (!tipo) return r
  if (!(await chiedi(tipo === 'codice'))) return r
  return operazione()
}

/** Come sopra per le API di Plancia (`riautenticazione_richiesta` in un 401). */
export async function conRiautenticazione<T>(operazione: () => Promise<T>): Promise<T> {
  try {
    return await operazione()
  } catch (e) {
    const corpo = e instanceof ErroreApi ? (e.corpo as { riautenticazione_richiesta?: boolean } | null) : null
    if (!(e instanceof ErroreApi) || e.stato !== 401 || !corpo?.riautenticazione_richiesta) throw e
    if (!(await chiedi(false))) throw e
    return operazione()
  }
}
