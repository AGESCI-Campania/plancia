<script setup lang="ts">
/** Cache dei PDF dei diari: generazione massiva per edizione (con avanzamento), elenco e invalidazione. */
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import CachePdfEdizione from '@/components/impostazioni/CachePdfEdizione.vue'
import CachePdfProgresso from '@/components/impostazioni/CachePdfProgresso.vue'
import type { EdizioneCachePdf } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const avvisi = useAvvisiStore()
const edizioni = useRichiesta(() => api.get<EdizioneCachePdf[]>('/impostazioni/cache-pdf'))
onMounted(edizioni.esegui)

const inCorso = computed(() => (edizioni.dati.value ?? []).filter((e) => e.generazione_in_corso && e.task_id))
const conCache = computed(() => (edizioni.dati.value ?? []).filter((e) => e.pdf_in_cache > 0))

const scelta = ref<number | ''>('')
const azione = useSalvataggio()

async function genera(): Promise<void> {
  const ed = edizioni.dati.value?.find((e) => e.id === scelta.value)
  if (!ed) return
  if (!(await conferma(`Avviare la generazione di tutti i PDF di ${ed.nome}? Durante la generazione i PDF singoli di questa edizione sono disabilitati.`, { testoConferma: 'Avvia' }))) return
  const r = await azione.esegui(() => api.post<{ detail: string }>('/impostazioni/cache-pdf/genera', { edizione_id: ed.id }))
  if (r) {
    avvisi.mostra(r.detail, 'success', 8000)
    scelta.value = ''
    await edizioni.esegui()
  }
}

async function invalidaTutto(): Promise<void> {
  if (!(await conferma('Eliminare TUTTI i PDF dalla cache, di tutte le edizioni?', { testoConferma: 'Elimina tutti', pericolosa: true }))) return
  const r = await azione.esegui(() => api.post<{ detail: string }>('/impostazioni/cache-pdf/invalida', { edizione_id: null }))
  if (r) {
    avvisi.mostra(r.detail, 'success', 8000)
    await edizioni.esegui()
  }
}
</script>

<template>
  <h1 class="h3 mb-5">Cache PDF dei diari</h1>

  <StatoCaricamento :in-corso="edizioni.inCorso.value && !edizioni.dati.value" :errore="edizioni.errore.value" @riprova="edizioni.esegui">
    <section class="card mb-6" aria-labelledby="titolo-genera">
      <div class="card-body">
        <h2 id="titolo-genera" class="h5"><IconaBs nome="file-earmark-pdf" class="me-2" />Genera tutti i PDF di un'edizione</h2>
        <p class="small fg-2">
          Avvia un'elaborazione che genera i PDF di tutti i diari inviati dell'edizione scelta, li carica
          su Drive e manda un aggiornamento per email ogni 10 diari. Durante la generazione i PDF singoli
          di quell'edizione sono disabilitati.
        </p>
        <form class="row align-items-end" novalidate @submit.prevent="genera">
          <div class="md:col-5 mb-3">
            <label for="edizione-genera" class="form-label">Edizione</label>
            <select id="edizione-genera" v-model="scelta" class="form-control" required>
              <option value="" disabled>— seleziona —</option>
              <option v-for="e in edizioni.dati.value" :key="e.id" :value="e.id" :disabled="e.generazione_in_corso">
                {{ e.nome }}{{ e.generazione_in_corso ? ' (generazione in corso…)' : '' }}
              </option>
            </select>
          </div>
          <div class="md:col-auto mb-3">
            <button type="submit" class="btn btn-solid theme-danger" :disabled="scelta === '' || azione.inCorso.value">
              <IconaBs nome="play-fill" class="me-1" />Avvia generazione massiva
            </button>
          </div>
        </form>
      </div>
    </section>

    <section v-if="inCorso.length" class="card mb-6 border-warning" aria-labelledby="titolo-in-corso">
      <div class="card-body">
        <h2 id="titolo-in-corso" class="h5 mb-4"><IconaBs nome="hourglass-split" class="me-2" />Generazione in corso</h2>
        <CachePdfProgresso v-for="e in inCorso" :key="`${e.id}-${e.task_id}`" :edizione="e" @finito="edizioni.esegui" />
      </div>
    </section>

    <template v-if="conCache.length">
      <CachePdfEdizione v-for="e in conCache" :key="e.id" :edizione="e" @cambiata="edizioni.esegui" />
      <div class="d-flex justify-content-end mb-6">
        <button type="button" class="btn btn-solid theme-danger" :disabled="azione.inCorso.value" @click="invalidaTutto">
          <IconaBs nome="trash" class="me-1" />Invalida tutta la cache PDF
        </button>
      </div>
    </template>
    <div v-else class="card"><div class="card-body fg-2 small">Nessun PDF in cache.</div></div>
  </StatoCaricamento>
</template>
