<script setup lang="ts">
/** Log di generazione PDF ed Excel (più recenti prima), con il traceback degli errori. */
import { ref, watch } from 'vue'

import { api, type Pagina } from '@/api/http'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import type { LogExport } from '@/components/impostazioni/tipi'
import { dataOra } from '@/composables/impostazioni-editor'
import { useRichiesta } from '@/composables/richiesta'

const LIMITE = 50
const offset = ref(0)
const elenco = useRichiesta(() => api.get<Pagina<LogExport>>('/impostazioni/log-export', { limit: LIMITE, offset: offset.value }))
watch(offset, elenco.esegui, { immediate: true })

const dettaglio = ref<LogExport | null>(null)
const aperta = ref(false)
function mostra(log: LogExport): void {
  dettaglio.value = log
  aperta.value = true
}
const breve = (testo: string) => (testo.length > 80 ? `${testo.slice(0, 79)}…` : testo)
</script>

<template>
  <div class="d-flex flex-wrap align-items-end gap-3 mb-5">
    <div>
      <h1 class="h3 mb-1">Log generazione PDF / Excel</h1>
      <small class="fg-2">{{ elenco.dati.value?.count ?? 0 }} eventi</small>
    </div>
    <button type="button" class="btn btn-outline btn-sm theme-secondary ms-auto" :disabled="elenco.inCorso.value" @click="elenco.esegui">
      <IconaBs nome="arrow-repeat" class="me-1" />Aggiorna
    </button>
  </div>

  <StatoCaricamento
    :in-corso="elenco.inCorso.value && !elenco.dati.value"
    :errore="elenco.errore.value"
    :vuoto="!elenco.dati.value?.items.length"
    messaggio-vuoto="Nessun log disponibile."
    @riprova="elenco.esegui"
  >
    <div class="card">
      <div class="table-responsive">
        <table class="table align-middle mb-0">
          <thead>
            <tr>
              <th scope="col">Data</th>
              <th scope="col">Tipo</th>
              <th scope="col">Stato</th>
              <th scope="col">Diario / Edizione</th>
              <th scope="col">Utente</th>
              <th scope="col">Messaggio</th>
              <th scope="col"><span class="visually-hidden">Traceback</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in elenco.dati.value?.items" :key="log.id">
              <td class="small text-nowrap">{{ dataOra(log.creato_at) }}</td>
              <td><span class="badge fw-normal" :class="log.tipo === 'pdf_massivo' ? 'theme-primary' : 'theme-secondary'">{{ log.tipo_display }}</span></td>
              <td><span class="badge fw-normal" :class="log.stato === 'ok' ? 'theme-success' : 'theme-danger'">{{ log.stato_display }}</span></td>
              <td class="small">
                <span v-if="log.edizione" class="fg-2">{{ log.edizione }}</span><template v-if="log.edizione && log.diario"> — </template>{{ log.diario }}
              </td>
              <td class="small fg-2">{{ log.utente || '—' }}</td>
              <td class="small" :title="log.messaggio">{{ breve(log.messaggio) }}</td>
              <td class="text-end">
                <button
                  v-if="log.traceback_testo"
                  type="button"
                  class="btn btn-outline btn-sm theme-secondary"
                  :aria-label="`Traceback del ${dataOra(log.creato_at)}`"
                  title="Traceback"
                  @click="mostra(log)"
                >
                  <IconaBs nome="terminal" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <PaginazioneElenco v-model:offset="offset" :totale="elenco.dati.value?.count ?? 0" :limite="LIMITE" />
  </StatoCaricamento>

  <FinestraDialogo v-model:aperta="aperta" :titolo="dettaglio ? `Traceback — ${dettaglio.diario || dettaglio.edizione} — ${dataOra(dettaglio.creato_at)}` : 'Traceback'" class="dialog-xl">
    <p v-if="dettaglio?.messaggio" class="small">{{ dettaglio.messaggio }}</p>
    <pre class="impostazioni-log small p-4 rounded mb-0">{{ dettaglio?.traceback_testo }}</pre>
  </FinestraDialogo>
</template>

<style scoped>
.impostazioni-log {
  white-space: pre-wrap;
  word-break: break-all;
  background: #1e1e1e;
  color: #e6e6e6;
  max-height: 60vh;
  overflow: auto;
}
</style>
