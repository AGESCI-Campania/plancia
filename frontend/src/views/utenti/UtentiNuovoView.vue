<script setup lang="ts">
/**
 * Nuovo utente (staff): utente di staff senza codice socio (Admin, Segreteria, Incaricato EG;
 * riceve l'email per impostare la password) oppure account per un Socio capo importato.
 * I ruoli proposti sono quelli che l'API dice creabili da chi opera.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api, ErroreApi, type ErroriCampo } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import UtentiSelettoreSocio from '@/components/utenti/UtentiSelettoreSocio.vue'
import { messaggioErrore } from '@/components/utenti/formato'
import type { OpzioniUtenti, SocioAutocomplete, UtenteCreato } from '@/components/utenti/tipi'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

type Tipo = 'staff' | 'socio'
const CAMPI = ['first_name', 'last_name', 'email', 'ruolo', 'socio_id']

const route = useRoute()
const router = useRouter()
const avvisi = useAvvisiStore()
const opzioni = useRichiesta(() => api.get<OpzioniUtenti>('/utenti/opzioni'))

const tipo = ref<Tipo>(route.query.tipo === 'socio' ? 'socio' : 'staff')
const tipiDisponibili = computed<Tipo[]>(() => {
  const o = opzioni.dati.value
  if (!o) return []
  return [
    ...(o.ruoli_staff_creabili.length ? (['staff'] as const) : []),
    ...(o.ruoli_nominabili_da_socio.length ? (['socio'] as const) : []),
  ]
})
watch(tipiDisponibili, (t) => {
  if (t.length && !t.includes(tipo.value)) tipo.value = t[0]!
})
watch(tipo, (t) => void router.replace({ query: t === 'socio' ? { tipo: 'socio' } : {} }))

const inCorso = ref(false)
const errore = ref('')
const errori = ref<ErroriCampo>({})

// --- Staff -------------------------------------------------------------------------
const nome = ref('')
const cognome = ref('')
const email = ref('')
const ruoloStaff = ref('')

// --- Da Socio ------------------------------------------------------------------------
const socio = ref<SocioAutocomplete | null>(null)
const ruoloSocio = ref('')

watch(opzioni.dati, (o) => {
  if (o && !ruoloSocio.value && o.ruoli_nominabili_da_socio.length === 1)
    ruoloSocio.value = o.ruoli_nominabili_da_socio[0]!.chiave
})

async function invia(): Promise<void> {
  errore.value = ''
  errori.value = {}
  const locali: ErroriCampo = {}
  if (tipo.value === 'staff') {
    if (!nome.value.trim()) locali.first_name = ['Inserisci il nome.']
    if (!email.value.trim()) locali.email = ['Inserisci l’email.']
    if (!ruoloStaff.value) locali.ruolo = ['Scegli il ruolo.']
  } else {
    if (!socio.value) locali.socio_id = ['Scegli il socio.']
    if (!ruoloSocio.value) locali.ruolo = ['Scegli il ruolo.']
  }
  if (Object.keys(locali).length) {
    errori.value = locali
    return
  }
  inCorso.value = true
  try {
    const r =
      tipo.value === 'staff'
        ? await api.post<UtenteCreato>('/utenti/staff', {
            email: email.value.trim(),
            first_name: nome.value.trim(),
            last_name: cognome.value.trim(),
            ruolo: ruoloStaff.value,
          })
        : await api.post<UtenteCreato>('/utenti/da-socio', { socio_id: socio.value!.id, ruolo: ruoloSocio.value })
    avvisi.mostra(r.detail)
    await router.push(`/utenti/${r.utente.id}`)
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = e.errori
      errore.value = messaggioErrore(e.message, e.errori, CAMPI)
    } else errore.value = 'Errore imprevisto.'
  } finally {
    inCorso.value = false
  }
}

onMounted(opzioni.esegui)
</script>

<template>
  <div class="d-flex align-items-center gap-3 mb-6">
    <RouterLink to="/utenti" class="btn btn-subtle btn-sm theme-secondary" aria-label="Torna agli utenti">
      <IconaBs nome="arrow-left" />
    </RouterLink>
    <h1 class="h3 mb-0">Nuovo utente</h1>
  </div>

  <StatoCaricamento
    :in-corso="opzioni.inCorso.value"
    :errore="opzioni.errore.value"
    :vuoto="!!opzioni.dati.value && !tipiDisponibili.length"
    messaggio-vuoto="Il tuo ruolo non consente di creare utenti."
    @riprova="opzioni.esegui"
  >
    <div v-if="opzioni.dati.value" style="max-width: 40rem">
      <div v-if="tipiDisponibili.length > 1" class="nav nav-pills mb-6" role="radiogroup" aria-label="Tipo di utente">
        <button
          type="button"
          role="radio"
          class="nav-link"
          :class="{ active: tipo === 'staff' }"
          :aria-checked="tipo === 'staff'"
          @click="tipo = 'staff'"
        >
          <IconaBs nome="person-badge" class="me-2" />Utente di staff
        </button>
        <button
          type="button"
          role="radio"
          class="nav-link"
          :class="{ active: tipo === 'socio' }"
          :aria-checked="tipo === 'socio'"
          @click="tipo = 'socio'"
        >
          <IconaBs nome="person-vcard" class="me-2" />Da Socio importato
        </button>
      </div>

      <div v-if="errore" class="alert theme-danger" role="alert">{{ errore }}</div>

      <form class="card" novalidate @submit.prevent="invia">
        <div v-if="tipo === 'staff'" class="card-body">
          <h2 class="h5">Utente di staff</h2>
          <p class="fg-2 small mb-5">
            Per le funzioni di amministrazione (Admin, Segreteria, Incaricato EG): non serve un codice
            socio AGESCI. L'utente riceve un'email con il link per impostare la password e accedere.
          </p>
          <CampoForm v-model="nome" etichetta="Nome" autocomplete="given-name" obbligatorio :errori="errori.first_name" />
          <CampoForm v-model="cognome" etichetta="Cognome" autocomplete="family-name" :errori="errori.last_name" />
          <CampoForm
            v-model="email"
            etichetta="Email"
            tipo="email"
            inputmode="email"
            autocomplete="email"
            obbligatorio
            :errori="errori.email"
          />
          <div class="mb-5">
            <label for="nuovo-ruolo-staff" class="form-label">Ruolo</label>
            <select
              id="nuovo-ruolo-staff"
              v-model="ruoloStaff"
              class="form-control"
              :class="{ 'is-invalid': errori.ruolo?.length }"
              required
            >
              <option value="" disabled>Scegli…</option>
              <option v-for="r in opzioni.dati.value.ruoli_staff_creabili" :key="r.chiave" :value="r.chiave">
                {{ r.etichetta }}
              </option>
            </select>
            <div v-for="e in errori.ruolo ?? []" :key="e" class="invalid-feedback">{{ e }}</div>
          </div>
          <p class="small fg-2">
            <IconaBs nome="info-circle" class="me-1" />Se l'email non arriva, l'utente può usare
            "Password dimenticata" dalla pagina di accesso.
          </p>
          <button type="submit" class="btn btn-solid theme-primary" :disabled="inCorso">
            <IconaBs nome="person-plus" class="me-2" />Crea utente e invia l'email
          </button>
        </div>

        <div v-else class="card-body">
          <h2 class="h5">Account da Socio importato</h2>
          <p class="fg-2 small mb-5">
            Scegli un capo importato, il ruolo, e crea l'account. Potrà ricevere l'invito dalla pagina
            <RouterLink to="/gestione/inviti">Inviti</RouterLink>.
          </p>
          <UtentiSelettoreSocio v-model="socio" etichetta="Socio (capo)" categoria="capo" obbligatorio :errori="errori.socio_id" />
          <div class="mb-5">
            <label for="nuovo-ruolo-socio" class="form-label">Ruolo</label>
            <select
              id="nuovo-ruolo-socio"
              v-model="ruoloSocio"
              class="form-control"
              :class="{ 'is-invalid': errori.ruolo?.length }"
              required
            >
              <option value="" disabled>Scegli…</option>
              <option v-for="r in opzioni.dati.value.ruoli_nominabili_da_socio" :key="r.chiave" :value="r.chiave">
                {{ r.etichetta }}
              </option>
            </select>
            <div v-for="e in errori.ruolo ?? []" :key="e" class="invalid-feedback">{{ e }}</div>
          </div>
          <button type="submit" class="btn btn-solid theme-primary" :disabled="inCorso">
            <IconaBs nome="person-plus" class="me-2" />Crea account
          </button>
        </div>
      </form>
    </div>
  </StatoCaricamento>
</template>
