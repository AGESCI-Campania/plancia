<script setup lang="ts">
/**
 * Il mio profilo: dati e Socio, cambio email (solo per chi può, oggi il Capo Squadriglia),
 * ruoli e storico nomine, ultimi accessi, sessioni attive con "termina le altre", account
 * social collegati (scollegamento via allauth). Password e MFA sono in `profilo/sicurezza`.
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { allauth, erroriAllauth } from '@/api/allauth'
import { api, ErroreApi } from '@/api/http'
import type { Me } from '@/api/tipi'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import UtentiBadgeRuolo from '@/components/utenti/UtentiBadgeRuolo.vue'
import UtentiTabellaAccessi from '@/components/utenti/UtentiTabellaAccessi.vue'
import UtentiTabellaNomine from '@/components/utenti/UtentiTabellaNomine.vue'
import { dataOra, descriviBrowser } from '@/components/utenti/formato'
import type { Profilo, Sessione, SocialAccount } from '@/components/utenti/tipi'
import { conferma } from '@/composables/conferma'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'
import { useSessioneStore } from '@/stores/sessione'

const sessione = useSessioneStore()
const avvisi = useAvvisiStore()
const profilo = useRichiesta(() => api.get<Profilo>('/me/profilo'))
const sessioni = useRichiesta(() => api.get<Sessione[]>('/me/sessioni'))
const u = computed(() => profilo.dati.value?.utente)
/** Prima questa sessione, poi le altre dalla più recente. */
const sessioniOrdinate = computed(() =>
  [...(sessioni.dati.value ?? [])].sort(
    (a, b) => Number(b.corrente) - Number(a.corrente) || b.ultimo_accesso.localeCompare(a.ultimo_accesso),
  ),
)
const altreSessioni = computed(() => (sessioni.dati.value ?? []).filter((s) => !s.corrente).length)

// --- Email ---------------------------------------------------------------------------------
const modificaEmail = ref(false)
const email = ref('')
const erroriEmail = ref<string[]>([])
const salvataggio = ref(false)

function apriEmail(): void {
  email.value = u.value?.email ?? ''
  erroriEmail.value = []
  modificaEmail.value = true
}

async function salvaEmail(): Promise<void> {
  erroriEmail.value = []
  if (!email.value.trim()) {
    erroriEmail.value = ['Inserisci l’indirizzo email.']
    return
  }
  salvataggio.value = true
  try {
    sessione.me = await api.patch<Me>('/me', { email: email.value.trim() })
    modificaEmail.value = false
    avvisi.mostra('Indirizzo email aggiornato.')
    await profilo.esegui()
  } catch (e) {
    erroriEmail.value = e instanceof ErroreApi ? (e.errori.email ?? e.errori.__all__ ?? [e.message]) : ['Errore imprevisto.']
  } finally {
    salvataggio.value = false
  }
}

// --- Sessioni --------------------------------------------------------------------------------
async function terminaAltre(): Promise<void> {
  const ok = await conferma('Terminare tutte le sessioni attive tranne questa? Sugli altri dispositivi dovrai accedere di nuovo.', {
    titolo: 'Termina le altre sessioni',
    testoConferma: 'Termina',
    pericolosa: true,
  })
  if (!ok) return
  try {
    const r = await api.post<{ terminate: number; detail: string }>('/me/sessioni/termina-altre')
    avvisi.mostra(r.detail)
    await sessioni.esegui()
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Operazione non riuscita.', 'danger')
  }
}

// --- Account social ------------------------------------------------------------------------
async function scollega(sa: SocialAccount): Promise<void> {
  const ok = await conferma(`Scollegare l'account ${sa.nome_provider} (${sa.email || sa.uid})?`, {
    titolo: 'Scollega account',
    testoConferma: 'Scollega',
    pericolosa: true,
  })
  if (!ok) return
  try {
    const r = await allauth.scollegaProvider(sa.provider, sa.uid)
    if (r.status === 200) {
      avvisi.mostra('Account scollegato.')
      await profilo.esegui()
    } else {
      const errori = erroriAllauth(r)
      avvisi.mostra(Object.values(errori).flat().join(' ') || 'Account non scollegato.', 'danger')
    }
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Account non scollegato.', 'danger')
  }
}

function iconaProvider(provider: string): string {
  return { google: 'google', apple: 'apple', microsoft: 'microsoft', sestante: 'compass' }[provider] ?? 'person-circle'
}

onMounted(() => {
  void profilo.esegui()
  void sessioni.esegui()
})
</script>

<template>
  <h1 class="h3 mb-6">Il mio profilo</h1>

  <StatoCaricamento :in-corso="profilo.inCorso.value && !u" :errore="u ? '' : profilo.errore.value" @riprova="profilo.esegui">
    <div v-if="u && profilo.dati.value" class="grid">
        <section class="card g-col-12 md:g-col-6" aria-labelledby="titolo-account">
          <div class="card-body">
            <h2 id="titolo-account" class="h5">Dati account</h2>
            <dl>
              <dt>Nome</dt>
              <dd>{{ u.nome_completo }}</dd>
              <dt>Email</dt>
              <dd class="text-break">{{ u.email }}</dd>
              <dt>Ruolo attivo</dt>
              <dd><UtentiBadgeRuolo :ruolo="u.ruolo" /></dd>
              <template v-if="u.ruoli_attivi.length > 1">
                <dt>Altri ruoli</dt>
                <dd class="d-flex flex-wrap gap-2">
                  <UtentiBadgeRuolo
                    v-for="r in u.ruoli_attivi.filter((x) => x.chiave !== u!.ruolo.chiave)"
                    :key="r.chiave"
                    :ruolo="r"
                  />
                </dd>
              </template>
              <template v-if="u.socio">
                <dt>Gruppo</dt>
                <dd>{{ u.socio.gruppo ?? '—' }}</dd>
                <dt>Zona</dt>
                <dd>{{ u.socio.zona ?? '—' }}</dd>
                <dt>Codice socio</dt>
                <dd><code>{{ u.socio.codice_socio }}</code></dd>
              </template>
              <dt>Verifica in due passaggi</dt>
              <dd class="mb-0">
                <span class="badge" :class="u.mfa_attiva ? 'theme-success' : 'theme-secondary'">
                  {{ u.mfa_attiva ? 'Attiva' : 'Non attiva' }}
                </span>
                <span v-if="u.mfa_richiesta && !u.mfa_attiva" class="small fg-2 ms-2">obbligatoria per il tuo ruolo</span>
              </dd>
            </dl>
            <div class="d-flex flex-wrap gap-3">
              <button
                v-if="u.puo_modificare_email && !modificaEmail"
                type="button"
                class="btn btn-outline btn-sm theme-primary"
                @click="apriEmail"
              >
                <IconaBs nome="envelope" class="me-1" />Modifica email
              </button>
              <RouterLink to="/profilo/sicurezza" class="btn btn-outline btn-sm theme-secondary">
                <IconaBs nome="key" class="me-1" />Password e sicurezza
              </RouterLink>
            </div>
            <form v-if="modificaEmail" class="mt-5" novalidate @submit.prevent="salvaEmail">
              <CampoForm
                v-model="email"
                etichetta="Nuovo indirizzo email"
                tipo="email"
                inputmode="email"
                autocomplete="email"
                obbligatorio
                :errori="erroriEmail"
              />
              <div class="d-flex gap-3">
                <button type="submit" class="btn btn-solid btn-sm theme-primary" :disabled="salvataggio">Salva</button>
                <button type="button" class="btn btn-text btn-sm theme-secondary" @click="modificaEmail = false">Annulla</button>
              </div>
            </form>
          </div>
        </section>

        <section class="card g-col-12 md:g-col-6" aria-labelledby="titolo-sessioni">
          <div class="card-body">
            <h2 id="titolo-sessioni" class="h5">Sessioni attive</h2>
            <StatoCaricamento :in-corso="sessioni.inCorso.value && !sessioni.dati.value" :errore="sessioni.errore.value" @riprova="sessioni.esegui">
              <ul class="list-group mb-5">
                <li v-for="s in sessioniOrdinate" :key="s.id" class="list-group-item">
                  <div class="d-flex align-items-center gap-2">
                    <IconaBs nome="laptop" />
                    <strong>{{ descriviBrowser(s.user_agent) }}</strong>
                    <span v-if="s.corrente" class="badge theme-success ms-auto">Questa sessione</span>
                  </div>
                  <div class="small fg-2">
                    IP <code>{{ s.ip || '—' }}</code> · ultimo uso {{ dataOra(s.ultimo_accesso) }} · dal {{ dataOra(s.creato_at) }}
                  </div>
                </li>
              </ul>
              <button
                type="button"
                class="btn btn-outline btn-sm theme-danger"
                :disabled="altreSessioni === 0"
                @click="terminaAltre"
              >
                <IconaBs nome="box-arrow-right" class="me-1" />Termina le altre sessioni
              </button>
            </StatoCaricamento>
          </div>
        </section>

        <section v-if="profilo.dati.value.social_accounts.length" class="card g-col-12" aria-labelledby="titolo-social">
          <div class="card-body">
            <h2 id="titolo-social" class="h5">Account collegati</h2>
            <ul class="list-group">
              <li
                v-for="sa in profilo.dati.value.social_accounts"
                :key="sa.id"
                class="list-group-item d-flex align-items-center gap-3"
              >
                <IconaBs :nome="iconaProvider(sa.provider)" />
                <div class="flex-grow-1 text-break">
                  <div class="fw-semibold">{{ sa.nome_provider }}</div>
                  <div class="small fg-2">{{ sa.email || sa.uid }}</div>
                </div>
                <button type="button" class="btn btn-text btn-sm theme-danger" @click="scollega(sa)">
                  Scollega<span class="visually-hidden"> {{ sa.nome_provider }}</span>
                </button>
              </li>
            </ul>
          </div>
        </section>

        <section class="card g-col-12" aria-labelledby="titolo-nomine">
          <div class="card-body">
            <h2 id="titolo-nomine" class="h5">Storico nomine</h2>
            <UtentiTabellaNomine :nomine="profilo.dati.value.nomine" />
          </div>
        </section>
        <section class="card g-col-12" aria-labelledby="titolo-accessi">
          <div class="card-body">
            <h2 id="titolo-accessi" class="h5">Ultimi accessi</h2>
            <UtentiTabellaAccessi :accessi="profilo.dati.value.accessi" />
          </div>
        </section>
    </div>
  </StatoCaricamento>
</template>
