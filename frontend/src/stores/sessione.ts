import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { allauth, type Flusso, type RispostaAllauth } from '@/api/allauth'
import { api, ErroreApi } from '@/api/http'
import type { FlagMenu, Me } from '@/api/tipi'

/**
 * Sessione dell'utente: stato di allauth (autenticato, passi in sospeso come la MFA) e
 * profilo Plancia (`/api/v1/me`, ruolo attivo e flag dei menu calcolati dal backend).
 * Le guardie del router usano solo questo store; i permessi veri restano nel backend.
 */
export const useSessioneStore = defineStore('sessione', () => {
  const me = ref<Me | null>(null)
  const flussi = ref<Flusso[]>([])
  const caricata = ref(false)

  const autenticato = computed(() => me.value !== null)
  /** Primo passo di login in sospeso (es. `mfa_authenticate`), se c'è. */
  const passoInSospeso = computed(() => flussi.value.find((f) => f.is_pending)?.id ?? null)

  function puo(flag: FlagMenu): boolean {
    return Boolean(me.value?.menu?.[flag])
  }

  async function caricaProfilo(): Promise<void> {
    try {
      me.value = await api.get<Me>('/me')
    } catch (e) {
      if (e instanceof ErroreApi && e.stato === 401) me.value = null
      else throw e
    }
  }

  /** Interpreta una risposta di allauth: 200 autenticato, 401 con eventuali passi in sospeso. */
  async function applica(r: RispostaAllauth): Promise<RispostaAllauth> {
    flussi.value = r.data?.flows ?? []
    if (r.status === 200 && r.meta?.is_authenticated !== false) await caricaProfilo()
    else me.value = null
    return r
  }

  async function carica(): Promise<void> {
    try {
      await applica(await allauth.sessione())
    } finally {
      caricata.value = true
    }
  }

  async function esci(): Promise<void> {
    await allauth.esci()
    me.value = null
    flussi.value = []
  }

  async function cambiaRuolo(ruolo: string): Promise<void> {
    await api.post('/me/ruolo', { ruolo })
    await caricaProfilo()
  }

  return {
    me,
    flussi,
    caricata,
    autenticato,
    passoInSospeso,
    puo,
    applica,
    carica,
    caricaProfilo,
    esci,
    cambiaRuolo,
  }
})
