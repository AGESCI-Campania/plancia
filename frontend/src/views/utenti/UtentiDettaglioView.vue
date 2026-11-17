<script setup lang="ts">
/**
 * Dettaglio utente (staff): dati e Socio, ruoli attivi, assegnazione di un ruolo, storico
 * delle nomine con revoca, ultimi accessi, impersonazione. Cosa si può fare lo dice l'API
 * (`ruoli_nominabili`, `puo_impersonare`); i controlli veri restano nel backend.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroreApi, type ErroriCampo } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import UtentiBadgeRuolo from '@/components/utenti/UtentiBadgeRuolo.vue'
import UtentiTabellaAccessi from '@/components/utenti/UtentiTabellaAccessi.vue'
import UtentiTabellaNomine from '@/components/utenti/UtentiTabellaNomine.vue'
import { messaggioErrore } from '@/components/utenti/formato'
import type { EdizioneBreve, Nomina, UtenteDettaglio } from '@/components/utenti/tipi'
import { conferma } from '@/composables/conferma'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'
import { useSessioneStore } from '@/stores/sessione'

const props = defineProps<{ id: number }>()
const avvisi = useAvvisiStore()
const sessione = useSessioneStore()

const utente = useRichiesta(() => api.get<UtenteDettaglio>(`/utenti/${props.id}`))
const edizioni = useRichiesta(() => api.get<EdizioneBreve[]>('/edizioni'))

const u = computed(() => utente.dati.value)
const sonoIo = computed(() => sessione.me?.id === props.id)

watch(u, (dati) => {
  if (dati) document.title = `${dati.nome_completo} · Plancia`
})

// --- Assegna ruolo -------------------------------------------------------------------
const ruolo = ref('')
const edizioneId = ref('')
const scadenza = ref('')
const errori = ref<ErroriCampo>({})
const erroreNomina = ref('')
const inCorso = ref(false)

watch(u, (dati) => {
  if (dati && !dati.ruoli_nominabili.some((r) => r.chiave === ruolo.value)) {
    ruolo.value = dati.ruoli_nominabili.find((r) => r.chiave === dati.ruolo.chiave)?.chiave ?? ''
  }
})

async function nomina(): Promise<void> {
  if (!u.value) return
  errori.value = {}
  erroreNomina.value = ''
  if (!ruolo.value) {
    errori.value = { ruolo: ['Scegli il ruolo.'] }
    return
  }
  inCorso.value = true
  try {
    const n = await api.post<Nomina>(`/utenti/${props.id}/nomine`, {
      ruolo: ruolo.value,
      edizione_id: edizioneId.value ? Number(edizioneId.value) : null,
      scadenza: scadenza.value || null,
    })
    avvisi.mostra(`Ruolo ${n.ruolo.etichetta} assegnato a ${u.value.nome_completo}.`)
    edizioneId.value = ''
    scadenza.value = ''
    await utente.esegui()
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = e.errori
      erroreNomina.value = messaggioErrore(e.message, e.errori, ['ruolo', 'edizione_id', 'scadenza'])
    } else erroreNomina.value = 'Errore imprevisto.'
  } finally {
    inCorso.value = false
  }
}

// --- Revoca ----------------------------------------------------------------------------
/** Pulsante "Revoca" solo per ruoli che chi opera può assegnare (l'API ricontrolla). */
function revocabile(n: Nomina): boolean {
  return (
    !sonoIo.value &&
    n.attiva &&
    !n.da_sso &&
    Boolean(u.value?.ruoli_nominabili.some((r) => r.chiave === n.ruolo.chiave))
  )
}

async function revoca(n: Nomina): Promise<void> {
  if (!u.value) return
  const ok = await conferma(
    `Revocare il ruolo ${n.ruolo.etichetta} a ${u.value.nome_completo}? La nomina resta nello storico.`,
    { titolo: 'Revoca nomina', testoConferma: 'Revoca', pericolosa: true },
  )
  if (!ok) return
  try {
    await api.post(`/utenti/${props.id}/nomine/${n.id}/revoca`)
    avvisi.mostra(`Ruolo ${n.ruolo.etichetta} revocato.`)
    await utente.esegui()
  } catch (e) {
    avvisi.mostra(
      e instanceof ErroreApi ? messaggioErrore(e.message, e.errori) : 'Revoca non riuscita.',
      'danger',
    )
  }
}

// --- Impersonazione ----------------------------------------------------------------------
async function impersona(): Promise<void> {
  if (!u.value) return
  const ok = await conferma(
    `Operare come ${u.value.nome_completo}? Vedrai Plancia come la vede questo utente finché non torni al tuo account.`,
    { titolo: 'Impersona utente', testoConferma: 'Impersona' },
  )
  if (!ok) return
  try {
    await api.post(`/utenti/${props.id}/impersona`)
    // La sessione è cambiata (anche il token CSRF): si ricarica l'app da capo.
    window.location.assign('/')
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Impersonazione non riuscita.', 'danger')
  }
}

watch(
  () => props.id,
  () => void utente.esegui(),
)
onMounted(() => {
  void utente.esegui()
  void edizioni.esegui()
})
</script>

<template>
  <StatoCaricamento :in-corso="utente.inCorso.value && !u" :errore="u ? '' : utente.errore.value" @riprova="utente.esegui">
    <template v-if="u">
      <div class="d-flex flex-wrap align-items-center gap-3 mb-6">
        <RouterLink to="/utenti" class="btn btn-subtle btn-sm theme-secondary" aria-label="Torna agli utenti">
          <IconaBs nome="arrow-left" />
        </RouterLink>
        <h1 class="h3 mb-0">{{ u.nome_completo }}</h1>
        <UtentiBadgeRuolo :ruolo="u.ruolo" />
        <button
          v-if="u.puo_impersonare"
          type="button"
          class="btn btn-outline theme-warning ms-auto"
          @click="impersona"
        >
          <IconaBs nome="incognito" class="me-2" />Impersona utente
        </button>
      </div>

      <div class="grid">
          <section class="card g-col-12 md:g-col-6" aria-labelledby="titolo-dati">
            <div class="card-body">
              <h2 id="titolo-dati" class="h5">Dati</h2>
              <dl class="mb-0">
                <dt>Email</dt>
                <dd class="text-break">{{ u.email }}</dd>
                <template v-if="u.socio">
                  <dt>Codice socio</dt>
                  <dd><code>{{ u.socio.codice_socio }}</code></dd>
                  <dt>Categoria</dt>
                  <dd>{{ u.socio.categoria_display }}</dd>
                  <dt>Gruppo</dt>
                  <dd>{{ u.socio.gruppo ?? '—' }}</dd>
                  <dt>Zona</dt>
                  <dd>{{ u.socio.zona ?? '—' }}</dd>
                </template>
                <dt>Ruoli attivi</dt>
                <dd class="d-flex flex-wrap gap-2">
                  <UtentiBadgeRuolo v-for="r in u.ruoli_attivi" :key="r.chiave" :ruolo="r" />
                  <span v-if="!u.ruoli_attivi.length" class="fg-2">Nessuno</span>
                </dd>
                <dt>Account attivo</dt>
                <dd>
                  <span class="badge" :class="u.is_active ? 'theme-success' : 'theme-danger'">{{ u.is_active ? 'Sì' : 'No' }}</span>
                </dd>
                <dt>Accesso al pannello Django</dt>
                <dd class="mb-0">{{ u.is_staff ? 'Sì' : 'No' }}<template v-if="u.is_superuser"> (superutente)</template></dd>
              </dl>
            </div>
          </section>

          <section v-if="u.ruoli_nominabili.length" class="card g-col-12 md:g-col-6" aria-labelledby="titolo-nomina">
            <form class="card-body" novalidate @submit.prevent="nomina">
              <h2 id="titolo-nomina" class="h5">Assegna ruolo</h2>
              <div v-if="erroreNomina" class="alert theme-danger" role="alert">{{ erroreNomina }}</div>
              <div class="mb-5">
                <label for="nomina-ruolo" class="form-label">Ruolo</label>
                <select
                  id="nomina-ruolo"
                  v-model="ruolo"
                  class="form-control"
                  :class="{ 'is-invalid': errori.ruolo?.length }"
                  required
                >
                  <option value="" disabled>Scegli…</option>
                  <option v-for="r in u.ruoli_nominabili" :key="r.chiave" :value="r.chiave">{{ r.etichetta }}</option>
                </select>
                <div v-for="e in errori.ruolo ?? []" :key="e" class="invalid-feedback">{{ e }}</div>
              </div>
              <div class="mb-5">
                <label for="nomina-edizione" class="form-label">Edizione</label>
                <select
                  id="nomina-edizione"
                  v-model="edizioneId"
                  class="form-control"
                  :class="{ 'is-invalid': errori.edizione_id?.length }"
                  aria-describedby="nomina-edizione-aiuto"
                >
                  <option value="">Nessuna</option>
                  <option v-for="ed in edizioni.dati.value ?? []" :key="ed.id" :value="String(ed.id)">
                    Edizione {{ ed.anno }}
                  </option>
                </select>
                <div id="nomina-edizione-aiuto" class="form-text">Solo per Capo Reparto e Capo Squadriglia.</div>
                <div v-for="e in errori.edizione_id ?? []" :key="e" class="invalid-feedback">{{ e }}</div>
              </div>
              <div class="mb-5">
                <label for="nomina-scadenza" class="form-label">Scadenza (facoltativa)</label>
                <input
                  id="nomina-scadenza"
                  v-model="scadenza"
                  type="date"
                  class="form-control"
                  :class="{ 'is-invalid': errori.scadenza?.length }"
                />
                <div v-for="e in errori.scadenza ?? []" :key="e" class="invalid-feedback">{{ e }}</div>
              </div>
              <button type="submit" class="btn btn-solid theme-primary" :disabled="inCorso">Conferma nomina</button>
            </form>
          </section>

          <section class="card g-col-12" aria-labelledby="titolo-nomine">
            <div class="card-body">
              <h2 id="titolo-nomine" class="h5">Storico nomine</h2>
              <UtentiTabellaNomine :nomine="u.nomine" :revocabile="revocabile" @revoca="revoca" />
            </div>
          </section>
          <section class="card g-col-12" aria-labelledby="titolo-accessi">
            <div class="card-body">
              <h2 id="titolo-accessi" class="h5">Ultimi accessi</h2>
              <UtentiTabellaAccessi :accessi="u.accessi" con-provider />
            </div>
          </section>
      </div>
    </template>
  </StatoCaricamento>
</template>
