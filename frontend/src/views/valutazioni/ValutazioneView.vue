<script setup lang="ts">
/**
 * Valutazione di un diario (`/diari/{id}/valutazione`): stato ed esito, assegnazione alla
 * Pattuglia GV, valutazione diretta, proposta, conferma/rigetto della proposta, modifica e
 * pubblicazione. Cosa mostrare lo decidono le `azioni` dell'API; mai al Capo Squadriglia
 * (l'API risponde 403 e la pagina mostra solo il messaggio).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import type {
  AzioniValutazione,
  DiarioDettaglio,
  SocioAutocomplete,
  Valutazione,
} from '@/api/tipi-edizioni'
import BadgeStato from '@/components/BadgeStato.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import ValutazioniFormEsito from '@/components/valutazioni/ValutazioniFormEsito.vue'
import ValutazioniSelettorePgv from '@/components/valutazioni/ValutazioniSelettorePgv.vue'
import { conferma } from '@/composables/conferma'
import {
  coloreEsito,
  ESITI,
  ESITI_PROPOSTA,
  formatoDataOra,
  messaggioAccessoValutazione,
} from '@/composables/edizioni'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ id: number }>()
const avvisi = useAvvisiStore()

const diario = ref<DiarioDettaglio | null>(null)
const valutazione = ref<Valutazione | null>(null)
/** Azioni quando la valutazione non esiste ancora (il dettaglio risponde 404). */
const azioniSenzaValutazione = ref<AzioniValutazione | null>(null)
const inCorso = ref(true)
const errore = ref('')
const occupato = ref('')

const azioni = computed<AzioniValutazione | null>(
  () => valutazione.value?.azioni ?? azioniSenzaValutazione.value,
)
const nessunaAzione = computed(() => !azioni.value || !Object.values(azioni.value).some(Boolean))
const inRevisione = computed(() => valutazione.value?.stato === 'in_revisione')

async function carica(): Promise<void> {
  inCorso.value = true
  errore.value = ''
  azioniSenzaValutazione.value = null
  try {
    try {
      valutazione.value = await api.get<Valutazione>(`/diari/${props.id}/valutazione`)
    } catch (e) {
      if (!(e instanceof ErroreApi) || e.stato !== 404) throw e
      // Nessuna valutazione ancora (o diario inesistente: lo dice la richiesta delle azioni)
      valutazione.value = null
      azioniSenzaValutazione.value = await api.get<AzioniValutazione>(`/diari/${props.id}/valutazione/azioni`)
    }
    diario.value = await api.get<DiarioDettaglio>(`/diari/${props.id}`).catch(() => null)
  } catch (e) {
    valutazione.value = null
    errore.value =
      e instanceof ErroreApi ? messaggioAccessoValutazione(e.stato, e.message) : 'Valutazione non caricata.'
  } finally {
    inCorso.value = false
  }
}
onMounted(carica)
watch(() => props.id, carica)

/** Esegue un'azione che restituisce la valutazione aggiornata. */
async function esegui(nome: string, percorso: string, corpo: unknown, messaggio: string): Promise<boolean> {
  occupato.value = nome
  try {
    valutazione.value = await api.post<Valutazione>(`/diari/${props.id}/valutazione/${percorso}`, corpo)
    azioniSenzaValutazione.value = null
    avvisi.mostra(messaggio)
    return true
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Operazione non riuscita.', 'danger')
    return false
  } finally {
    occupato.value = ''
  }
}

const valuta = (d: { esito: string; note: string }) => esegui('valuta', 'valuta', d, 'Valutazione registrata.')
const proponi = (d: { esito: string; note: string }) =>
  esegui('proposta', 'proposta', d, "Proposta registrata. In attesa di conferma dall'Incaricato.")
const modifica = (d: { esito: string; note: string }) => esegui('modifica', 'modifica', d, 'Valutazione aggiornata.')

const noteConferma = ref('')
async function confermaProposta(): Promise<void> {
  if (await esegui('conferma', 'conferma', { note: noteConferma.value.trim() }, 'Proposta confermata.')) {
    noteConferma.value = ''
  }
}

async function rigettaProposta(): Promise<void> {
  const ok = await conferma('La proposta della Pattuglia GV viene scartata e il diario torna in valutazione.', {
    titolo: 'Rigettare la proposta?',
    testoConferma: 'Rigetta',
    pericolosa: true,
  })
  if (ok) await esegui('rigetta', 'rigetta', undefined, 'Proposta rigettata. Il diario torna in valutazione.')
}

const pgv = ref<SocioAutocomplete | null>(null)
const selettore = ref<InstanceType<typeof ValutazioniSelettorePgv>>()
async function assegna(): Promise<void> {
  if (!pgv.value?.user_pk) return
  const nome = pgv.value.label
  if (await esegui('assegna', 'assegna-pgv', { pgv_pk: pgv.value.user_pk }, `Diario assegnato a ${nome}.`)) {
    selettore.value?.azzera()
  }
}

async function pubblica(): Promise<void> {
  const ok = await conferma(
    "L'esito diventa visibile al Capo Reparto e non si può più modificare.",
    { titolo: "Pubblicare l'esito?", testoConferma: 'Pubblica' },
  )
  if (!ok) return
  occupato.value = 'pubblica'
  try {
    await api.post(`/diari/${props.id}/valutazione/pubblica`)
    avvisi.mostra('Esito pubblicato.')
    await carica()
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Pubblicazione non riuscita.', 'danger')
  } finally {
    occupato.value = ''
  }
}
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-3 mb-6">
    <RouterLink :to="`/diari/${id}`" class="btn btn-outline btn-sm theme-secondary">
      <IconaBs nome="arrow-left" class="me-1" />Diario
    </RouterLink>
    <h1 class="h4 mb-0">
      Valutazione<template v-if="diario">: {{ diario.squadriglia }}
        <small class="fg-2 fw-normal">({{ diario.reparto }} · {{ diario.edizione_anno }})</small></template>
    </h1>
  </div>

  <StatoCaricamento :in-corso="inCorso" :errore="errore" @riprova="carica">
    <div class="row g-6">
      <div class="col-12 md:col-6">
        <section class="card" aria-labelledby="titolo-stato-valutazione">
          <div class="card-header"><h2 id="titolo-stato-valutazione" class="h6 mb-0">Stato valutazione</h2></div>
          <div class="card-body">
            <dl class="row mb-0">
              <dt class="col-5">Stato diario</dt>
              <dd class="col-7">
                <BadgeStato
                  v-if="diario || valutazione?.diario_stato"
                  :stato="diario?.stato ?? valutazione?.diario_stato ?? ''"
                  :etichetta="diario?.stato_display"
                />
                <template v-else>—</template>
              </dd>
              <dt class="col-5">Esito</dt>
              <dd class="col-7">
                <span v-if="valutazione?.esito" class="badge" :class="`theme-${coloreEsito(valutazione.esito)}`">
                  {{ valutazione.esito_display }}
                </span>
                <template v-else>—</template>
              </dd>
              <dt class="col-5">Stato valutazione</dt>
              <dd class="col-7">{{ valutazione?.stato_display ?? 'Non ancora valutato' }}</dd>
              <template v-if="valutazione?.proposta_esito">
                <dt class="col-5">Proposta Pattuglia GV</dt>
                <dd class="col-7">{{ valutazione.proposta_esito_display }}</dd>
              </template>
              <template v-if="valutazione?.note">
                <dt class="col-5">Note</dt>
                <dd class="col-7 plancia-note">{{ valutazione.note }}</dd>
              </template>
              <template v-if="valutazione?.valutatore">
                <dt class="col-5">Valutato da</dt>
                <dd class="col-7">{{ valutazione.valutatore }}</dd>
              </template>
              <template v-if="valutazione?.confermata_da">
                <dt class="col-5">Confermato da</dt>
                <dd class="col-7">{{ valutazione.confermata_da }}</dd>
              </template>
              <template v-if="valutazione?.aggiornata_at">
                <dt class="col-5">Ultima modifica</dt>
                <dd class="col-7">{{ formatoDataOra(valutazione.aggiornata_at) }}</dd>
              </template>
              <dt class="col-5">Pubblicato</dt>
              <dd class="col-7 mb-0">
                <span v-if="valutazione?.pubblicata" class="badge theme-success">Sì</span>
                <template v-else>No</template>
              </dd>
            </dl>
          </div>
        </section>
      </div>

      <div class="col-12 md:col-6">
        <!-- Proposta della Pattuglia GV in revisione: serve la conferma dell'Incaricato -->
        <section v-if="azioni?.puo_confermare" class="card card-subtle theme-warning mb-5" aria-labelledby="titolo-proposta">
          <div class="card-header">
            <h2 id="titolo-proposta" class="h6 mb-0">Proposta della Pattuglia GV in attesa di conferma</h2>
          </div>
          <div class="card-body">
            <p>Proposta: <strong>{{ valutazione?.proposta_esito_display }}</strong></p>
            <div class="mb-4">
              <label for="note-conferma" class="form-label">Note (facoltative)</label>
              <textarea id="note-conferma" v-model="noteConferma" class="form-control" rows="2" />
            </div>
            <div class="d-flex flex-wrap gap-2 mb-4">
              <button type="button" class="btn btn-solid btn-sm theme-success" :disabled="!!occupato" @click="confermaProposta">
                Conferma proposta
              </button>
              <button v-if="azioni.puo_rigettare" type="button" class="btn btn-outline btn-sm theme-danger" :disabled="!!occupato" @click="rigettaProposta">
                Rigetta proposta
              </button>
            </div>
            <details v-if="azioni.puo_valutare_direttamente">
              <summary class="small fg-2">Ignora la proposta e valuta direttamente</summary>
              <div class="mt-4">
                <ValutazioniFormEsito :esiti="ESITI" testo-invio="Valuta direttamente" tema="secondary" :in-corso="occupato === 'valuta'" @invia="valuta" />
              </div>
            </details>
          </div>
        </section>

        <section v-else-if="azioni?.puo_valutare_direttamente" class="card mb-5" aria-labelledby="titolo-valuta">
          <div class="card-header"><h2 id="titolo-valuta" class="h6 mb-0">Valuta direttamente</h2></div>
          <div class="card-body">
            <ValutazioniFormEsito :esiti="ESITI" testo-invio="Conferma valutazione" :in-corso="occupato === 'valuta'" @invia="valuta" />
          </div>
        </section>

        <section v-else-if="azioni?.puo_modificare" class="card mb-5" aria-labelledby="titolo-modifica">
          <div class="card-header"><h2 id="titolo-modifica" class="h6 mb-0">Modifica esito</h2></div>
          <div class="card-body">
            <p class="small fg-2">L'esito si può cambiare fino alla pubblicazione.</p>
            <ValutazioniFormEsito
              :esiti="ESITI"
              testo-invio="Aggiorna valutazione"
              :esito-iniziale="valutazione?.esito"
              :note-iniziali="valutazione?.note"
              :in-corso="occupato === 'modifica'"
              @invia="modifica"
            />
          </div>
        </section>

        <section v-if="azioni?.puo_proporre" class="card mb-5" aria-labelledby="titolo-proponi">
          <div class="card-header"><h2 id="titolo-proponi" class="h6 mb-0">Proponi valutazione</h2></div>
          <div class="card-body">
            <p v-if="inRevisione" class="alert theme-info small" role="status">
              La tua proposta ({{ valutazione?.proposta_esito_display }}) è in attesa di conferma da
              parte di un Incaricato EG. Puoi ancora cambiarla.
            </p>
            <ValutazioniFormEsito
              :esiti="ESITI_PROPOSTA"
              testo-invio="Proponi"
              :esito-iniziale="valutazione?.proposta_esito"
              :in-corso="occupato === 'proposta'"
              @invia="proponi"
            />
          </div>
        </section>

        <button
          v-if="azioni?.puo_pubblicare"
          type="button"
          class="btn btn-solid theme-success w-100 mb-5"
          :disabled="!!occupato"
          @click="pubblica"
        >
          <IconaBs nome="megaphone" class="me-1" />Pubblica esito
        </button>

        <p v-if="nessunaAzione && !valutazione" class="fg-2">Il diario non è ancora stato valutato.</p>
        <p v-else-if="valutazione?.pubblicata" class="alert theme-success" role="status">
          <IconaBs nome="check-circle" class="me-1" />Esito pubblicato.
        </p>
      </div>

      <div v-if="azioni?.puo_assegnare_pgv" class="col-12">
        <section class="card" aria-labelledby="titolo-assegnazioni">
          <div class="card-header"><h2 id="titolo-assegnazioni" class="h6 mb-0">Assegnazioni Pattuglia GV</h2></div>
          <div class="card-body">
            <ul v-if="valutazione?.assegnazioni.length" class="list-unstyled d-flex flex-wrap gap-2 mb-4">
              <li v-for="a in valutazione.assegnazioni" :key="a.pgv_pk">
                <span class="badge theme-secondary" :title="a.pgv_email">{{ a.pgv_nome }}</span>
              </li>
            </ul>
            <p v-else class="fst-italic fg-2">Nessun membro assegnato.</p>
            <form class="d-flex flex-wrap gap-2 align-items-start" @submit.prevent="assegna">
              <div class="flex-grow-1 plancia-selettore-pgv">
                <ValutazioniSelettorePgv ref="selettore" v-model="pgv" />
              </div>
              <button type="submit" class="btn btn-outline theme-primary" :disabled="!pgv || occupato === 'assegna'">Assegna</button>
            </form>
          </div>
        </section>
      </div>
    </div>
  </StatoCaricamento>
</template>

<style scoped>
.plancia-note {
  white-space: pre-line;
}
.plancia-selettore-pgv {
  min-width: min(100%, 17rem);
  max-width: 28rem;
}
</style>
