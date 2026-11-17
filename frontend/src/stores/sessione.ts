import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { allauth, type Flusso, type RispostaAllauth } from '@/api/allauth'
import { api, ErroreApi } from '@/api/http'
import type { FlagMenu, Me } from '@/api/tipi'
import { conferma } from '@/composables/conferma'
import { associaUtente, dimenticaLetture, inAttesa, sincronizzaCoda, svuotaDatiOffline } from '@/offline/coda'

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
      // I dati offline sono di questo utente (se erano di un altro si cancellano)
      await associaUtente(me.value.id)
    } catch (e) {
      if (e instanceof ErroreApi && e.stato === 401) {
        me.value = null
        // Sessione scaduta: restano solo le modifiche non inviate, per lo stesso utente
        await dimenticaLetture().catch(() => undefined)
      } else throw e
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

  /** Logout; `false` se l'utente ha rinunciato per non perdere modifiche non inviate. */
  async function esci(): Promise<boolean> {
    const restano = inAttesa.value ? await sincronizzaCoda() : 0
    if (
      restano > 0 &&
      !(await conferma(
        `Ci sono ${restano} modifiche fatte offline non ancora inviate: uscendo verranno cancellate da questo dispositivo.`,
        { titolo: 'Uscire comunque?', testoConferma: 'Esci e cancella', pericolosa: true },
      ))
    )
      return false
    await allauth.esci()
    // Dati di minori sul dispositivo: si cancellano a ogni logout (decisione 5 del piano)
    await svuotaDatiOffline()
    me.value = null
    flussi.value = []
    return true
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
