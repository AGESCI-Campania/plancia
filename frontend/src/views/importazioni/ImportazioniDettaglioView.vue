<script setup lang="ts">
/**
 * Dettaglio di un import: riepilogo, righe da riconciliare (Capo Reparto) con selettore
 * Socio, "Riprova anomalie" per gli import squadriglie, righe scartate e CSV degli scarti.
 * Sostituisce `templates/imports/log_detail.html`.
 */
import { reactive, ref, watch } from 'vue'

import { api, ErroreApi } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import {
  campiValorizzati,
  dataOra,
  etichettaEdizione,
  righeScartate,
  tipoAvvisoRiprova,
  type EsitoRiconcilia,
  type EsitoRiprova,
  type LogImportazioneDettaglio,
  type SocioAutocomplete,
} from '@/components/importazioni/importazioni'
import ImportazioniSelettoreSocio from '@/components/importazioni/ImportazioniSelettoreSocio.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { scaricaESalva } from '@/composables/file'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ id: string }>()
const avvisi = useAvvisiStore()

const log = useRichiesta(() => api.get<LogImportazioneDettaglio>(`/importazioni/log/${props.id}`))
watch(() => props.id, () => void log.esegui(), { immediate: true })

// --- Riconciliazione manuale ------------------------------------------------------------
const scelte = reactive<Record<number, SocioAutocomplete | null>>({})
const erroriRiga = reactive<Record<number, string[]>>({})
const inAssociazione = ref<number | null>(null)

async function associa(rigaId: number): Promise<void> {
  const socio = scelte[rigaId]
  if (!socio) {
    erroriRiga[rigaId] = ['Seleziona un Socio capo.']
    return
  }
  erroriRiga[rigaId] = []
  inAssociazione.value = rigaId
  try {
    const esito = await api.post<EsitoRiconcilia>(`/importazioni/righe/${rigaId}/riconcilia`, { socio_pk: socio.id })
    avvisi.mostra(esito.messaggio)
    delete scelte[rigaId]
    await log.esegui()
  } catch (e) {
    const err = e instanceof ErroreApi ? e : null
    erroriRiga[rigaId] = err ? (Object.values(err.errori).flat().length ? Object.values(err.errori).flat() : [err.message]) : ['Errore imprevisto.']
  } finally {
    inAssociazione.value = null
  }
}

// --- Riprova anomalie ---------------------------------------------------------------------
const inRiprova = ref(false)
async function riprova(): Promise<void> {
  inRiprova.value = true
  try {
    const esito = await api.post<EsitoRiprova>(`/importazioni/log/${props.id}/riprova`)
    avvisi.mostra(esito.messaggio, tipoAvvisoRiprova(esito.risolte, esito.ancora_aperte), 8000)
    await log.esegui()
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Errore imprevisto.', 'danger')
  } finally {
    inRiprova.value = false
  }
}

// --- CSV degli scarti -----------------------------------------------------------------------
const inScarico = ref(false)
async function scaricaScarti(): Promise<void> {
  inScarico.value = true
  try {
    await scaricaESalva(`/api/v1/importazioni/log/${props.id}/scarti.csv`)
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Scaricamento non riuscito.', 'danger')
  } finally {
    inScarico.value = false
  }
}
</script>

<template>
  <StatoCaricamento :in-corso="log.inCorso.value && !log.dati.value" :errore="log.errore.value" @riprova="log.esegui()">
    <template v-if="log.dati.value">
      <div class="d-flex flex-wrap align-items-center gap-3 mb-5">
        <RouterLink :to="{ name: 'importazioni' }" class="btn btn-outline theme-secondary btn-sm">
          <IconaBs nome="arrow-left" class="me-1" />Storico
        </RouterLink>
        <h1 class="h4 mb-0">
          Import {{ log.dati.value.tipo_display }} del {{ dataOra(log.dati.value.creato_at) }}
        </h1>
      </div>

      <dl class="row mb-6">
        <dt class="col-12 sm:col-4 lg:col-3">File</dt>
        <dd class="col-12 sm:col-8 lg:col-9 text-break"><small class="font-monospace">{{ log.dati.value.file_nome }}</small></dd>
        <template v-if="log.dati.value.edizione_anno">
          <dt class="col-12 sm:col-4 lg:col-3">Edizione</dt>
          <dd class="col-12 sm:col-8 lg:col-9">{{ etichettaEdizione({ anno: log.dati.value.edizione_anno }) }}</dd>
        </template>
        <template v-if="log.dati.value.creato_da">
          <dt class="col-12 sm:col-4 lg:col-3">Avviato da</dt>
          <dd class="col-12 sm:col-8 lg:col-9">{{ log.dati.value.creato_da }}</dd>
        </template>
        <dt class="col-12 sm:col-4 lg:col-3">Totale righe</dt>
        <dd class="col-12 sm:col-8 lg:col-9">{{ log.dati.value.totale }}</dd>
        <dt class="col-12 sm:col-4 lg:col-3">OK</dt>
        <dd class="col-12 sm:col-8 lg:col-9"><span class="fg-success fw-semibold">{{ log.dati.value.ok }}</span></dd>
        <dt class="col-12 sm:col-4 lg:col-3">Scartate</dt>
        <dd class="col-12 sm:col-8 lg:col-9"><span class="fg-danger fw-semibold">{{ log.dati.value.scartati }}</span></dd>
        <dt class="col-12 sm:col-4 lg:col-3">Da riconciliare</dt>
        <dd class="col-12 sm:col-8 lg:col-9">
          <span v-if="log.dati.value.da_riconciliare" class="badge theme-warning">{{ log.dati.value.da_riconciliare }}</span>
          <span v-else class="fg-success">Nessuna</span>
        </dd>
      </dl>

      <!-- Righe da riconciliare -->
      <section v-if="log.dati.value.righe_da_riconciliare.length" aria-labelledby="titolo-anomalie" class="mb-7">
        <div class="d-flex flex-wrap align-items-center gap-3 mb-2">
          <h2 id="titolo-anomalie" class="h5 mb-0">
            Anomalie da riconciliare <span class="fg-2">(Capo Reparto)</span>
          </h2>
          <button
            v-if="log.dati.value.e_squadriglie"
            type="button"
            class="btn btn-solid theme-warning btn-sm"
            :disabled="inRiprova"
            @click="riprova"
          >
            <span v-if="inRiprova" class="spinner-border spinner-sm me-1" aria-hidden="true" />
            <IconaBs v-else nome="arrow-repeat" class="me-1" />Riprova anomalie
          </button>
        </div>
        <p class="small fg-2 mb-4">
          <template v-if="log.dati.value.e_squadriglie">
            Usa <strong>Riprova anomalie</strong> per abbinare automaticamente i Capi Reparto ora presenti
            (dopo un nuovo import capi o un inserimento manuale). Per le anomalie residue usa la
            riconciliazione manuale qui sotto.
          </template>
          <template v-else>Per ogni riga, cerca il Socio capo corrispondente e premi <strong>Associa</strong>.</template>
          Puoi cercare per nome, cognome, gruppo, zona o codice socio.
        </p>

        <article
          v-for="riga in log.dati.value.righe_da_riconciliare"
          :key="riga.id"
          class="card mb-4 plancia-riga-anomalia"
          :aria-labelledby="`riga-${riga.id}-titolo`"
        >
          <div class="card-body">
            <div class="row g-4 align-items-start">
              <div class="col-12 md:col-5">
                <h3 :id="`riga-${riga.id}-titolo`" class="small fg-2 fw-normal mb-1">
                  Riga {{ riga.numero }}
                  <template v-if="riga.note"> — <span class="fg-emphasis-warning">{{ riga.note }}</span></template>
                </h3>
                <table class="table table-sm table-borderless mb-0 plancia-dati-grezzi">
                  <tbody>
                    <tr v-for="[k, v] in campiValorizzati(riga.dati_grezzi)" :key="k">
                      <th scope="row" class="fg-2 fw-normal pe-2">{{ k }}</th>
                      <td class="text-break">{{ v }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <form class="col-12 md:col-7" novalidate @submit.prevent="associa(riga.id)">
                <ImportazioniSelettoreSocio
                  v-model="scelte[riga.id]"
                  etichetta="Seleziona il Capo Reparto"
                  categoria="capo"
                  :errori="erroriRiga[riga.id]"
                />
                <button type="submit" class="btn btn-solid theme-primary btn-sm mt-2" :disabled="inAssociazione === riga.id">
                  <span v-if="inAssociazione === riga.id" class="spinner-border spinner-sm me-1" aria-hidden="true" />
                  Associa<span class="visually-hidden"> la riga {{ riga.numero }}</span>
                </button>
              </form>
            </div>
          </div>
        </article>
      </section>
      <div v-else class="alert theme-success" role="status">Tutte le righe sono state riconciliate.</div>

      <!-- Righe scartate -->
      <div v-if="log.dati.value.scartati && !log.dati.value.righe_scartate.length" class="alert theme-warning mt-6" role="alert">
        <IconaBs nome="exclamation-triangle" class="me-1" />
        <strong>{{ righeScartate(log.dati.value.scartati) }}</strong>
        ma i dettagli non sono stati salvati (errore interno durante il salvataggio del log).
        Ricarica il file per ottenere il dettaglio degli errori.
      </div>
      <section v-else-if="log.dati.value.righe_scartate.length" class="mt-6" aria-labelledby="titolo-scartate">
        <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
          <h2 id="titolo-scartate" class="h5 mb-0">
            <IconaBs nome="x-circle" class="fg-danger me-1" />Righe scartate
            <span class="badge theme-danger ms-1">{{ log.dati.value.righe_scartate.length }}</span>
          </h2>
          <button type="button" class="btn btn-outline theme-secondary btn-sm ms-auto" :disabled="inScarico" @click="scaricaScarti">
            <span v-if="inScarico" class="spinner-border spinner-sm me-1" aria-hidden="true" />
            <IconaBs v-else nome="download" class="me-1" />Scarica CSV
          </button>
        </div>
        <p class="small fg-2 mb-4">
          Queste righe sono state escluse durante l'import a causa di un errore. Il motivo è riportato
          nella colonna <em>Errore</em>.
        </p>
        <div class="table-responsive">
          <table class="table table-sm table-hover align-middle small">
            <caption class="visually-hidden">Righe scartate e motivo dell'errore</caption>
            <thead>
              <tr>
                <th scope="col" class="text-nowrap">#</th>
                <th scope="col">Dati principali</th>
                <th scope="col">Errore</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="riga in log.dati.value.righe_scartate" :key="riga.id">
                <td class="fg-2 font-monospace">{{ riga.numero }}</td>
                <td class="plancia-dati-scarto">
                  <span v-for="[k, v] in campiValorizzati(riga.dati_grezzi)" :key="k" class="me-2 d-inline-block">
                    <span class="fg-2 plancia-chiave">{{ k }}:</span> {{ v }}
                  </span>
                </td>
                <td><span class="fg-danger">{{ riga.note || '—' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </StatoCaricamento>
</template>

<style scoped>
.plancia-riga-anomalia {
  border-color: var(--bs-warning-border, #ffc107);
}
.plancia-dati-grezzi {
  font-size: 0.82rem;
}
.plancia-dati-grezzi th {
  width: 1%;
  white-space: nowrap;
}
.plancia-dati-scarto {
  min-width: 16rem;
}
.plancia-chiave {
  font-size: 0.75rem;
}
</style>
