<script setup lang="ts">
/**
 * Dashboard statistiche per zona: scelta dell'edizione, indicatori globali, grafici e tabella
 * per zona, ticket dell'helpdesk, "Pubblica tutti gli esiti confermati" (se il backend lo
 * consente). Sostituisce `templates/stats/dashboard.html`.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatisticheGraficoBarre from '@/components/statistiche/StatisticheGraficoBarre.vue'
import {
  rigaPubblicazione,
  rigaStatoTicket,
  righeTicket,
  righeZone,
  SERIE_ESITI,
  SERIE_PUBBLICAZIONE,
  SERIE_STATO_TICKET,
  SERIE_TICKET,
  type Statistiche,
} from '@/components/statistiche/grafici'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { conferma } from '@/composables/conferma'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const route = useRoute()
const router = useRouter()
const avvisi = useAvvisiStore()

const edizioneId = ref(typeof route.query.edizione === 'string' ? route.query.edizione : '')
const stat = useRichiesta(() =>
  api.get<Statistiche>('/statistiche', { edizione_id: edizioneId.value || undefined }),
)
watch(
  edizioneId,
  () => {
    void router.replace({ query: { ...route.query, edizione: edizioneId.value || undefined } })
    void stat.esegui()
  },
  { immediate: true },
)
// Senza scelta esplicita il backend sceglie l'edizione di riferimento: il selettore la mostra
const edizioneMostrata = computed({
  get: () => edizioneId.value || String(stat.dati.value?.edizione?.id ?? ''),
  set: (v: string) => (edizioneId.value = v),
})

const indicatori = computed(() => {
  const g = stat.dati.value?.globali
  if (!g) return []
  return [
    { etichetta: 'Totale diari', valore: g.totale, classe: '' },
    { etichetta: 'Approvati', valore: g.approvati, classe: 'fg-success' },
    { etichetta: 'Non approvati', valore: g.non_approvati, classe: 'fg-danger' },
    { etichetta: 'Pubblicati', valore: g.pubblicati, classe: '' },
    { etichetta: 'Inviati', valore: g.inviati, classe: '' },
    { etichetta: 'In compilazione', valore: g.in_compilazione, classe: 'fg-2' },
  ]
})

const STATI_EDIZIONE: Record<string, string> = {
  bozza: 'Bozza',
  aperta: 'Aperta',
  in_valutazione: 'In valutazione',
  chiusa: 'Chiusa',
}

// --- Pubblica tutti gli esiti confermati -----------------------------------------------------
const inPubblicazione = ref(false)
async function pubblicaTutti(): Promise<void> {
  const ed = stat.dati.value?.edizione
  if (!ed) return
  const ok = await conferma(
    `Pubblicare tutti gli esiti confermati dell'edizione ${ed.anno}? I Capi Reparto li vedranno subito.`,
    { titolo: 'Pubblica esiti', testoConferma: 'Pubblica tutti', pericolosa: true },
  )
  if (!ok) return
  inPubblicazione.value = true
  try {
    const r = await api.post<{ pubblicati: number }>(`/edizioni/${ed.id}/pubblica-esiti`)
    avvisi.mostra(
      r.pubblicati === 1 ? 'Pubblicato 1 esito.' : `Pubblicati ${r.pubblicati} esiti.`,
      r.pubblicati ? 'success' : 'info',
    )
    await stat.esegui()
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Errore imprevisto.', 'danger')
  } finally {
    inPubblicazione.value = false
  }
}
</script>

<template>
  <div class="d-flex flex-wrap align-items-end gap-3 mb-6">
    <h1 class="h3 mb-0 me-auto">Statistiche</h1>
    <div v-if="stat.dati.value?.edizioni.length">
      <label for="stat-edizione" class="form-label small mb-1">Edizione</label>
      <select id="stat-edizione" v-model="edizioneMostrata" class="form-control form-control-sm" :disabled="stat.inCorso.value">
        <option v-for="ed in stat.dati.value.edizioni" :key="ed.id" :value="String(ed.id)">
          Edizione {{ ed.anno }} ({{ STATI_EDIZIONE[ed.stato] ?? ed.stato }})
        </option>
      </select>
    </div>
  </div>

  <StatoCaricamento :in-corso="stat.inCorso.value && !stat.dati.value" :errore="stat.errore.value" @riprova="stat.esegui()">
    <template v-if="stat.dati.value">
      <div v-if="!stat.dati.value.edizione" class="alert theme-info" role="status">Nessuna edizione disponibile.</div>
      <div v-else :aria-busy="stat.inCorso.value">
        <!-- Indicatori globali -->
        <section aria-labelledby="titolo-globali" class="mb-7">
          <h2 id="titolo-globali" class="visually-hidden">Indicatori dell'edizione {{ stat.dati.value.edizione.anno }}</h2>
          <ul class="row g-3 list-unstyled mb-0">
            <li v-for="k in indicatori" :key="k.etichetta" class="col-6 md:col-4 xl:col-2">
              <div class="card h-100 text-center">
                <div class="card-body py-3">
                  <div class="h3 mb-0 plancia-numero" :class="k.classe">{{ k.valore }}</div>
                  <div class="small fg-2">{{ k.etichetta }}</div>
                </div>
              </div>
            </li>
          </ul>
        </section>

        <!-- Grafici -->
        <div class="row g-4 mb-7">
          <div class="col-12 lg:col-7">
            <section class="card h-100">
              <div class="card-body">
                <StatisticheGraficoBarre
                  titolo="Esiti per zona"
                  etichetta-riga="Zona"
                  :serie="SERIE_ESITI"
                  :righe="righeZone(stat.dati.value.per_zona)"
                />
              </div>
            </section>
          </div>
          <div class="col-12 lg:col-5">
            <section class="card h-100">
              <div class="card-body">
                <StatisticheGraficoBarre
                  v-if="stat.dati.value.globali"
                  titolo="Esiti pubblicati sul totale dei diari"
                  etichetta-riga="Diari"
                  :serie="SERIE_PUBBLICAZIONE"
                  :righe="[rigaPubblicazione(stat.dati.value.globali)]"
                />
              </div>
            </section>
          </div>
        </div>

        <!-- Per zona -->
        <section aria-labelledby="titolo-zone" class="mb-7">
          <h2 id="titolo-zone" class="h5 mb-3">Per zona</h2>
          <p v-if="!stat.dati.value.per_zona.length" class="fg-2">Nessun dato.</p>
          <div v-else class="table-responsive">
            <table class="table table-sm table-hover align-middle">
              <caption class="visually-hidden">Diari ed esiti per zona</caption>
              <thead>
                <tr>
                  <th scope="col">Zona</th>
                  <th scope="col" class="text-end">Totale</th>
                  <th scope="col" class="text-end">Approvati</th>
                  <th scope="col" class="text-end">Non approvati</th>
                  <th scope="col" class="text-end">Maggiori info</th>
                  <th scope="col" class="text-end">Pubblicati</th>
                  <th scope="col">% Approvati</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in stat.dati.value.per_zona" :key="r.zona.id">
                  <th scope="row" class="fw-normal">{{ r.zona.nome }}</th>
                  <td class="text-end">{{ r.totale }}</td>
                  <td class="text-end fg-success">{{ r.approvati }}</td>
                  <td class="text-end fg-danger">{{ r.non_approvati }}</td>
                  <td class="text-end">{{ r.maggiori_info }}</td>
                  <td class="text-end">{{ r.pubblicati }}</td>
                  <td class="plancia-col-percentuale">
                    <div
                      class="progress"
                      role="progressbar"
                      :aria-valuenow="r.percentuale_approvati"
                      aria-valuemin="0"
                      aria-valuemax="100"
                      :aria-label="`Approvati in ${r.zona.nome}`"
                    >
                      <div class="progress-bar" :style="{ width: `${r.percentuale_approvati}%` }" />
                    </div>
                    <span class="small plancia-numero">{{ r.percentuale_approvati }}%</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- Ticket -->
        <section v-if="stat.dati.value.ticket" aria-labelledby="titolo-ticket" class="mb-7">
          <h2 id="titolo-ticket" class="h5 mb-3">Ticket helpdesk</h2>
          <p>
            Totale: <strong>{{ stat.dati.value.ticket.totale }}</strong> — Aperti:
            <strong>{{ stat.dati.value.ticket.aperti }}</strong> — Chiusi:
            <strong>{{ stat.dati.value.ticket.chiusi }}</strong>
          </p>
          <div class="row g-4">
            <div class="col-12 lg:col-7">
              <section class="card h-100">
                <div class="card-body">
                  <StatisticheGraficoBarre
                    titolo="Ticket per categoria"
                    etichetta-riga="Categoria"
                    :serie="SERIE_TICKET"
                    :righe="righeTicket(stat.dati.value.ticket)"
                  />
                </div>
              </section>
            </div>
            <div class="col-12 lg:col-5">
              <section class="card h-100">
                <div class="card-body">
                  <StatisticheGraficoBarre
                    titolo="Ticket per stato"
                    etichetta-riga="Ticket"
                    :serie="SERIE_STATO_TICKET"
                    :righe="[rigaStatoTicket(stat.dati.value.ticket)]"
                  />
                </div>
              </section>
            </div>
          </div>
        </section>

        <!-- Pubblica tutti -->
        <template v-if="stat.dati.value.puo_pubblicare_esiti">
          <hr class="my-6" />
          <button type="button" class="btn btn-solid theme-primary" :disabled="inPubblicazione" @click="pubblicaTutti">
            <span v-if="inPubblicazione" class="spinner-border spinner-sm me-1" aria-hidden="true" />
            <IconaBs v-else nome="megaphone" class="me-1" />Pubblica tutti gli esiti confermati
          </button>
        </template>
      </div>
    </template>
  </StatoCaricamento>
</template>

<style scoped>
.plancia-numero {
  font-variant-numeric: tabular-nums;
}
.plancia-col-percentuale {
  min-width: 9rem;
}
.plancia-col-percentuale .progress {
  display: inline-flex;
  vertical-align: middle;
  width: calc(100% - 3rem);
  height: 0.85rem;
  margin-right: 0.4rem;
}
</style>
