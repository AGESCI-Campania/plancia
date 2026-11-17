<script setup lang="ts">
/**
 * Import tracciati: lancio (una scheda per tracciato) e storico paginato dei log con filtro
 * per tipo. Sostituisce `templates/imports/log_list.html`.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, type Pagina } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import ImportazioniSchedaTracciato from '@/components/importazioni/ImportazioniSchedaTracciato.vue'
import {
  dataOra,
  etichettaEdizione,
  ordinaTracciati,
  type EdizioneBreve,
  type LogImportazione,
  type Tracciato,
} from '@/components/importazioni/importazioni'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { useRichiesta } from '@/composables/richiesta'

const LIMITE = 30
const route = useRoute()
const router = useRouter()

// --- Tracciati ed edizioni per le schede di lancio ------------------------------------------
const tracciati = useRichiesta(async () => ordinaTracciati(await api.get<Tracciato[]>('/importazioni/tracciati')))
const edizioni = useRichiesta(async () =>
  (await api.get<EdizioneBreve[]>('/edizioni')).sort((a, b) => b.anno - a.anno),
)

// --- Storico (filtro e pagina nella query string: link condivisibili, "indietro" funziona) --
const tipo = ref(typeof route.query.tipo === 'string' ? route.query.tipo : '')
const offset = ref(Number(route.query.offset) || 0)
const storico = useRichiesta(() =>
  api.get<Pagina<LogImportazione>>('/importazioni/log', { tipo: tipo.value, limit: LIMITE, offset: offset.value }),
)
/** Tipi con uno storico: i tracciati che scrivono un log (Risposte EG invia una email). */
const tipiStorico = computed(() => (tracciati.dati.value ?? []).filter((t) => t.chiave !== 'risposte_eg'))

watch(tipo, () => {
  offset.value = 0
})
watch([tipo, offset], () => {
  void router.replace({ query: { ...route.query, tipo: tipo.value || undefined, offset: offset.value || undefined } })
  void storico.esegui()
})

onMounted(() => {
  void tracciati.esegui()
  void edizioni.esegui()
  void storico.esegui()
})

function avviato(): void {
  // Il task parte in background: il log compare quando il worker lo crea.
  void storico.esegui()
  setTimeout(() => void storico.esegui(), 3000)
}
</script>

<template>
  <h1 class="h3 mb-6">Import tracciati</h1>

  <section class="card mb-7" aria-labelledby="titolo-carica">
    <div class="card-header flex-row flex-wrap align-items-center gap-2">
      <IconaBs nome="cloud-upload" class="fg-success" />
      <h2 id="titolo-carica" class="h5 mb-0">Carica tracciato</h2>
    </div>
    <div class="card-body">
      <p class="small fg-2 mb-1">
        Carica il file e avvia l'import. L'ordine consigliato è:
        <strong>1. Capi</strong> → <strong>2. Squadriglie iscritte</strong> → <strong>3. Ragazzi</strong>
        (opzionale).
      </p>
      <p class="small fg-2 mb-5">
        L'import squadriglie iscritte crea i Capi Squadriglia (ragazzi) direttamente dal file; l'import
        Ragazzi è opzionale e aggiorna i dati tramite codice socio.
      </p>
      <StatoCaricamento :in-corso="tracciati.inCorso.value" :errore="tracciati.errore.value" @riprova="tracciati.esegui()">
        <div v-if="edizioni.errore.value" class="alert theme-warning small" role="alert">
          Elenco delle edizioni non disponibile: {{ edizioni.errore.value }}
        </div>
        <div class="row g-4">
          <div v-for="(t, i) in tracciati.dati.value ?? []" :key="t.chiave" class="col-12 md:col-6 xl:col-3">
            <ImportazioniSchedaTracciato :tracciato="t" :numero="i + 1" :edizioni="edizioni.dati.value ?? []" @avviato="avviato" />
          </div>
        </div>
      </StatoCaricamento>
    </div>
  </section>

  <section aria-labelledby="titolo-storico">
    <div class="d-flex flex-wrap align-items-end gap-3 mb-4">
      <h2 id="titolo-storico" class="h5 mb-0 me-auto">Storico import</h2>
      <div>
        <label for="filtro-tipo" class="form-label small mb-1">Tipo</label>
        <select id="filtro-tipo" v-model="tipo" class="form-control form-control-sm">
          <option value="">Tutti</option>
          <option v-for="t in tipiStorico" :key="t.chiave" :value="t.chiave">{{ t.etichetta }}</option>
        </select>
      </div>
      <button type="button" class="btn btn-outline theme-secondary btn-sm" :disabled="storico.inCorso.value" @click="storico.esegui()">
        <IconaBs nome="arrow-clockwise" class="me-1" />Aggiorna
      </button>
    </div>

    <StatoCaricamento
      :in-corso="storico.inCorso.value && !storico.dati.value"
      :errore="storico.errore.value"
      :vuoto="!storico.dati.value?.items.length"
      messaggio-vuoto="Nessun import eseguito."
      @riprova="storico.esegui()"
    >
      <!-- Desktop: tabella -->
      <div class="table-responsive d-none md:d-block">
        <table class="table table-hover align-middle">
          <caption class="visually-hidden">Storico delle importazioni</caption>
          <thead>
            <tr>
              <th scope="col">Data</th>
              <th scope="col">Tipo</th>
              <th scope="col">Edizione</th>
              <th scope="col">File</th>
              <th scope="col" class="text-end">Totale</th>
              <th scope="col" class="text-end">OK</th>
              <th scope="col" class="text-end">Scartati</th>
              <th scope="col" class="text-end">Anomalie</th>
              <th scope="col"><span class="visually-hidden">Azioni</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in storico.dati.value?.items" :key="log.id">
              <td class="text-nowrap">{{ dataOra(log.creato_at) }}</td>
              <td>{{ log.tipo_display }}</td>
              <td class="small fg-2">{{ log.edizione_anno ? etichettaEdizione({ anno: log.edizione_anno }) : '—' }}</td>
              <td class="plancia-import-file"><small class="font-monospace" :title="log.file_nome">{{ log.file_nome }}</small></td>
              <td class="text-end">{{ log.totale }}</td>
              <td class="text-end fg-success">{{ log.ok }}</td>
              <td class="text-end fg-danger">{{ log.scartati }}</td>
              <td class="text-end">
                <span v-if="log.da_riconciliare" class="badge theme-warning">{{ log.da_riconciliare }}</span>
                <span v-else>—</span>
              </td>
              <td class="text-end">
                <RouterLink :to="{ name: 'importazioni-dettaglio', params: { id: log.id } }" class="btn btn-outline theme-secondary btn-sm">
                  Dettaglio<span class="visually-hidden"> import del {{ dataOra(log.creato_at) }}</span>
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mobile: elenco -->
      <ul class="list-group md:d-none">
        <li v-for="log in storico.dati.value?.items" :key="log.id" class="list-group-item">
          <RouterLink :to="{ name: 'importazioni-dettaglio', params: { id: log.id } }" class="d-block fg-reset text-decoration-none">
            <div class="d-flex justify-content-between gap-2">
              <strong>{{ log.tipo_display }}</strong>
              <span class="small fg-2 text-nowrap">{{ dataOra(log.creato_at) }}</span>
            </div>
            <div class="small fg-2 text-truncate font-monospace">{{ log.file_nome }}</div>
            <div class="small d-flex flex-wrap gap-3 mt-1">
              <span v-if="log.edizione_anno">{{ etichettaEdizione({ anno: log.edizione_anno }) }}</span>
              <span>Totale {{ log.totale }}</span>
              <span class="fg-success">OK {{ log.ok }}</span>
              <span class="fg-danger">Scartati {{ log.scartati }}</span>
              <span v-if="log.da_riconciliare" class="badge theme-warning">{{ log.da_riconciliare }} anomalie</span>
            </div>
          </RouterLink>
        </li>
      </ul>

      <PaginazioneElenco v-model:offset="offset" :totale="storico.dati.value?.count ?? 0" :limite="LIMITE" />
    </StatoCaricamento>
  </section>
</template>

<style scoped>
.plancia-import-file {
  max-width: 16rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
