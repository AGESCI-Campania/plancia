<script setup lang="ts">
/**
 * Dettaglio del diario (`GET /diari/{id}`): intestazione con referenti e scadenze, stato
 * dei moduli 1–6 con i link alle pagine dei moduli, azioni secondo i `permessi` calcolati
 * dal backend (invio, riapertura, cambio referenti, dilazione, PDF), riquadro della
 * valutazione solo dove l'API la rende visibile, contenuto dei moduli.
 */
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import BadgeStato from '@/components/BadgeStato.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import DiariCambioReferente from '@/components/diari/DiariCambioReferente.vue'
import DiariContenutoModuli from '@/components/diari/DiariContenutoModuli.vue'
import DiariDilazione from '@/components/diari/DiariDilazione.vue'
import {
  formattaData,
  nomeReferente,
  STATI_DOPO_INVIO,
  vociModuli,
  type DiarioDettaglio,
  type StatoDiario,
  type ValutazioneApi,
} from '@/components/diari/diari'
import { conferma } from '@/composables/conferma'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ id: number }>()
const avvisi = useAvvisiStore()

const richiesta = useRichiesta(() => api.get<DiarioDettaglio>(`/diari/${props.id}`))
const diario = computed(() => richiesta.dati.value)
const permessi = computed(() => diario.value?.permessi)
const moduli = computed(() => (diario.value ? vociModuli(diario.value) : []))

// Valutazione: la chiede solo chi può vedere la relazione (mai il Capo Squadriglia) e solo
// dopo l'invio; l'API decide (staff, Pattuglia GV assegnata, Capo Reparto dopo la pubblicazione).
const valutazione = ref<ValutazioneApi | null>(null)
/** Valutazione non ancora creata ma l'utente può avviarla (assegnazione, valutazione diretta). */
const valutazioneDaAvviare = ref(false)
async function caricaValutazione(d: DiarioDettaglio): Promise<void> {
  valutazione.value = null
  valutazioneDaAvviare.value = false
  if (!d.permessi?.puo_vedere_relazione || !STATI_DOPO_INVIO.has(d.stato)) return
  try {
    valutazione.value = await api.get<ValutazioneApi>(`/diari/${d.id}/valutazione`)
  } catch (e) {
    if (!(e instanceof ErroreApi) || ![403, 404].includes(e.stato)) throw e
    if (e.stato !== 404) return
    // Diario appena inviato: nessuna valutazione ancora. Le azioni dicono se si può avviarla.
    try {
      const azioni = await api.get<{ azioni?: Record<string, unknown> } & Record<string, unknown>>(
        `/diari/${d.id}/valutazione/azioni`,
      )
      valutazioneDaAvviare.value = Object.values(azioni.azioni ?? azioni).some((v) => v === true)
    } catch {
      valutazioneDaAvviare.value = false
    }
  }
}
const riquadroValutazione = computed(() => {
  if (valutazione.value) {
    const v = valutazione.value
    return {
      esito: v.esito_display,
      stato: v.stato_display ?? v.stato,
      pubblicata: v.pubblicata,
      note: v.note,
      proposta: v.proposta_esito_display ?? null,
    }
  }
  const v = diario.value?.valutazione
  if (!v && valutazioneDaAvviare.value)
    return { esito: null, stato: 'Da valutare', pubblicata: false, note: '', proposta: null }
  return v
    ? {
        esito: v.esito_display,
        stato: v.stato,
        pubblicata: v.pubblicata,
        note: v.note,
        proposta: null,
      }
    : null
})

async function carica(): Promise<void> {
  const d = await richiesta.esegui()
  if (d) {
    document.title = `${d.squadriglia} · Plancia`
    await caricaValutazione(d).catch(() => undefined)
  }
}
watch(() => props.id, carica, { immediate: true })

// --- Azioni FSM --------------------------------------------------------------------------
const inCorso = ref('')

const AZIONI = {
  'csq-invia': {
    domanda:
      'Inviare la parte del Capo Squadriglia? Dopo l’invio i moduli 1–5 non saranno più modificabili e il Capo Reparto potrà compilare la relazione finale.',
    titolo: 'Invia al Capo Reparto',
    fatto:
      'Parte del Capo Squadriglia inviata. Il Capo Reparto può ora compilare la relazione finale.',
  },
  invia: {
    domanda:
      'Inviare il diario allo staff? Dopo l’invio il diario non sarà più modificabile e passerà alla valutazione.',
    titolo: 'Invia il diario allo staff',
    fatto: 'Diario inviato allo staff.',
  },
  riapri: {
    domanda:
      'Riaprire il diario per integrazioni? Tornerà in compilazione e il Capo Squadriglia potrà modificarlo.',
    titolo: 'Riapri per integrazioni',
    fatto: 'Diario riaperto per integrazioni.',
  },
} as const

async function esegui(azione: keyof typeof AZIONI): Promise<void> {
  const a = AZIONI[azione]
  if (!(await conferma(a.domanda, { titolo: a.titolo, testoConferma: a.titolo }))) return
  inCorso.value = azione
  try {
    await api.post<StatoDiario>(`/diari/${props.id}/azioni/${azione}`)
    avvisi.mostra(a.fatto)
    await carica()
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Operazione non riuscita.', 'danger', 8000)
  } finally {
    inCorso.value = ''
  }
}

const cambio = ref<'csq' | 'crp' | null>(null)
const cambioAperto = computed({
  get: () => cambio.value !== null,
  set: (v) => {
    if (!v) cambio.value = null
  },
})
const tipoCambio = ref<'csq' | 'crp'>('csq')
function apriCambio(tipo: 'csq' | 'crp'): void {
  tipoCambio.value = tipo
  cambio.value = tipo
}
const dilazioneAperta = ref(false)

const haAzioni = computed(() => {
  const p = permessi.value
  return Boolean(
    p &&
    (p.puo_inviare_csq ||
      p.puo_inviare ||
      p.puo_riaprire ||
      p.puo_cambiare_csq ||
      p.puo_cambiare_crp ||
      p.puo_concedere_dilazione ||
      p.puo_pdf),
  )
})
</script>

<template>
  <StatoCaricamento
    :in-corso="richiesta.inCorso.value && !diario"
    :errore="richiesta.errore.value"
    @riprova="carica"
  >
    <template v-if="diario">
      <!-- Intestazione -->
      <div class="d-flex flex-wrap align-items-start gap-5 mb-6">
        <div class="flex-grow-1 min-w-0">
          <h1 class="h3 mb-1">{{ diario.squadriglia }}</h1>
          <p class="fg-2 mb-3">
            Edizione {{ diario.edizione_anno }} — {{ diario.reparto }} · {{ diario.gruppo }} ·
            {{ diario.zona }}
          </p>
          <div class="d-flex flex-wrap gap-2">
            <BadgeStato :stato="diario.stato" :etichetta="diario.stato_display" class="fs-md" />
            <span class="badge theme-secondary fs-md">{{ diario.tipo_display }}</span>
            <span v-if="diario.pubblicato" class="badge theme-success fs-md">Esito pubblicato</span>
          </div>
        </div>
      </div>

      <div class="row g-6 mb-6">
        <!-- Referenti e scadenze -->
        <section class="col-12" :class="{ 'lg:col-7': haAzioni }" aria-labelledby="titolo-info">
          <div class="card h-100">
            <div class="card-body">
              <h2 id="titolo-info" class="visually-hidden">Informazioni</h2>
              <dl class="row g-3 mb-0 small">
                <div class="col-12 sm:col-6">
                  <dt>Capo Squadriglia</dt>
                  <dd class="mb-0">{{ nomeReferente(diario.csq) || '—' }}</dd>
                </div>
                <div class="col-12 sm:col-6">
                  <dt>Capo Reparto</dt>
                  <dd class="mb-0">{{ nomeReferente(diario.crp) || '—' }}</dd>
                </div>
                <div class="col-12 sm:col-6">
                  <dt>Scadenza</dt>
                  <dd class="mb-0">
                    <strong>{{
                      formattaData(diario.scadenze?.effettiva ?? diario.scadenza) || '—'
                    }}</strong>
                    <span v-if="diario.scadenze?.dilazionata" class="badge theme-warning ms-2">
                      <IconaBs nome="clock-history" class="me-1" />Dilazione concessa
                    </span>
                    <div v-if="diario.scadenze" class="fg-2">
                      {{ diario.scadenze.riferimento_display }}
                    </div>
                  </dd>
                </div>
                <div v-if="diario.scadenze" class="col-12 sm:col-6">
                  <dt>Scadenze dell'edizione</dt>
                  <dd class="mb-0">
                    Evento: {{ formattaData(diario.scadenze.evento) || '—' }}<br />
                    Assemblea: {{ formattaData(diario.scadenze.assemblea) || '—' }}
                  </dd>
                </div>
                <div v-if="diario.inviato_at" class="col-12 sm:col-6">
                  <dt>Inviato allo staff</dt>
                  <dd class="mb-0">{{ formattaData(diario.inviato_at) }}</dd>
                </div>
                <div v-if="diario.drive_folder_url" class="col-12 sm:col-6">
                  <dt>Cartella Drive</dt>
                  <dd class="mb-0">
                    <a :href="diario.drive_folder_url" target="_blank" rel="noopener"
                      ><IconaBs nome="google" class="me-1" />Apri gli allegati su Drive</a
                    >
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        </section>

        <!-- Azioni -->
        <section
          v-if="haAzioni && permessi"
          class="col-12 lg:col-5 order-first lg:order-last"
          aria-labelledby="titolo-azioni"
        >
          <div class="card h-100">
            <div class="card-body d-grid gap-3 align-content-start">
              <h2 id="titolo-azioni" class="h6 mb-1">Azioni</h2>
              <button
                v-if="permessi.puo_inviare_csq"
                type="button"
                class="btn btn-solid theme-primary"
                :disabled="inCorso !== ''"
                @click="esegui('csq-invia')"
              >
                <span
                  v-if="inCorso === 'csq-invia'"
                  class="spinner-border spinner-sm me-2"
                  aria-hidden="true"
                />
                <IconaBs v-else nome="send" class="me-2" />Invia al Capo Reparto
              </button>
              <button
                v-if="permessi.puo_inviare"
                type="button"
                class="btn btn-solid theme-success"
                :disabled="inCorso !== ''"
                @click="esegui('invia')"
              >
                <span
                  v-if="inCorso === 'invia'"
                  class="spinner-border spinner-sm me-2"
                  aria-hidden="true"
                />
                <IconaBs v-else nome="send-check" class="me-2" />Invia il diario allo staff
              </button>
              <RouterLink
                v-if="permessi.puo_pdf"
                :to="`/diari/${diario.id}/pdf`"
                class="btn btn-outline theme-secondary"
              >
                <IconaBs nome="file-earmark-pdf" class="me-2" />PDF del diario
              </RouterLink>
              <button
                v-if="permessi.puo_concedere_dilazione"
                type="button"
                class="btn btn-outline theme-warning"
                @click="dilazioneAperta = true"
              >
                <IconaBs nome="clock-history" class="me-2" />Concedi dilazione
              </button>
              <button
                v-if="permessi.puo_riaprire"
                type="button"
                class="btn btn-outline theme-warning"
                :disabled="inCorso !== ''"
                @click="esegui('riapri')"
              >
                <span
                  v-if="inCorso === 'riapri'"
                  class="spinner-border spinner-sm me-2"
                  aria-hidden="true"
                />
                <IconaBs v-else nome="arrow-counterclockwise" class="me-2" />Riapri per integrazioni
              </button>
              <button
                v-if="permessi.puo_cambiare_csq"
                type="button"
                class="btn btn-outline theme-secondary"
                @click="apriCambio('csq')"
              >
                <IconaBs nome="person-gear" class="me-2" />Cambia Capo Squadriglia
              </button>
              <button
                v-if="permessi.puo_cambiare_crp"
                type="button"
                class="btn btn-outline theme-secondary"
                @click="apriCambio('crp')"
              >
                <IconaBs nome="person-gear" class="me-2" />Cambia Capo Reparto
              </button>
              <RouterLink
                v-if="permessi.puo_cambiare_crp && diario.reparto_id"
                :to="`/reparti/${diario.reparto_id}/cambia-capo-reparto`"
                class="btn btn-text btn-sm theme-secondary"
              >
                Cambia il Capo Reparto di tutto il reparto
              </RouterLink>
            </div>
          </div>
        </section>
      </div>

      <!-- Valutazione (solo dove l'API la rende visibile) -->
      <section v-if="riquadroValutazione" class="card mb-6" aria-labelledby="titolo-valutazione">
        <div class="card-body d-flex flex-row flex-wrap align-items-center gap-5">
          <div class="flex-grow-1">
            <h2 id="titolo-valutazione" class="h6 mb-2">
              <IconaBs nome="clipboard-check" class="me-2" />Valutazione
            </h2>
            <p class="mb-1">
              <template v-if="riquadroValutazione.esito"
                >Esito: <strong>{{ riquadroValutazione.esito }}</strong></template
              >
              <template v-else>Esito non ancora deciso</template>
              <span
                class="badge ms-2"
                :class="riquadroValutazione.pubblicata ? 'theme-success' : 'theme-secondary'"
              >
                {{ riquadroValutazione.pubblicata ? 'Pubblicata' : 'Non pubblicata' }}
              </span>
            </p>
            <p class="small fg-2 mb-0">
              Stato: {{ riquadroValutazione.stato }}
              <template v-if="riquadroValutazione.proposta">
                · Proposta della Pattuglia GV: {{ riquadroValutazione.proposta }}</template
              >
            </p>
            <p v-if="riquadroValutazione.note" class="small mt-3 mb-0 plancia-diari-testo">
              {{ riquadroValutazione.note }}
            </p>
          </div>
          <RouterLink
            v-if="valutazione || valutazioneDaAvviare"
            :to="`/diari/${diario.id}/valutazione`"
            class="btn btn-outline theme-primary"
          >
            Apri la valutazione<IconaBs nome="arrow-right" class="ms-2" />
          </RouterLink>
        </div>
      </section>

      <!-- Stato dei moduli -->
      <section class="card mb-6" aria-labelledby="titolo-moduli">
        <div class="card-body">
          <h2 id="titolo-moduli" class="h6 mb-4">Stato della compilazione</h2>
          <ol class="list-unstyled row g-3 mb-0">
            <li v-for="m in moduli" :key="m.chiave" class="col-6 md:col-4 xl:col-2">
              <component
                :is="m.nonDisponibile ? 'span' : RouterLink"
                :to="m.nonDisponibile ? undefined : m.to"
                class="plancia-diari-modulo d-flex align-items-center gap-2 p-3 rounded-5 border h-100 small"
                :class="
                  m.compilato
                    ? 'plancia-diari-modulo--ok'
                    : m.facoltativo || m.nonDisponibile
                      ? 'fg-2 bg-1'
                      : 'plancia-diari-modulo--manca'
                "
                :aria-disabled="m.nonDisponibile ? 'true' : undefined"
              >
                <IconaBs :nome="m.compilato ? 'check-circle-fill' : 'circle'" />
                <span>
                  <span class="d-block fg-2">Modulo {{ m.numero }}</span>
                  {{ m.etichetta }}<template v-if="m.facoltativo"> (facoltativo)</template>
                  <span class="visually-hidden"
                    >: {{ m.compilato ? 'compilato' : 'da compilare' }}</span
                  >
                </span>
              </component>
            </li>
          </ol>
        </div>
      </section>

      <DiariContenutoModuli :diario="diario" @aggiorna="carica" />

      <DiariCambioReferente
        v-model:aperta="cambioAperto"
        :diario="diario"
        :tipo="tipoCambio"
        @cambiato="carica"
      />
      <DiariDilazione
        v-if="permessi?.puo_concedere_dilazione"
        v-model:aperta="dilazioneAperta"
        :diario="diario"
        @concessa="carica"
      />
    </template>
  </StatoCaricamento>
</template>

<style scoped>
.plancia-diari-modulo {
  text-decoration: none;
  color: inherit;
}
.plancia-diari-modulo--ok {
  background: var(--bs-success-bg-subtle);
  border-color: var(--bs-success-border) !important;
}
.plancia-diari-modulo--manca {
  background: var(--bs-warning-bg-subtle);
  border-color: var(--bs-warning-border) !important;
}
.plancia-diari-testo {
  white-space: pre-line;
}
dt {
  font-weight: 600;
}
</style>
