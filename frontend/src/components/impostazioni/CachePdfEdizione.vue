<script setup lang="ts">
/** PDF in cache di un'edizione: elenco paginato, eliminazione singola, invalidazione dell'edizione. */
import { ref, watch } from 'vue'

import { api, type Pagina } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import type { EdizioneCachePdf, FilePdf } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { dataOra, dimensioneLeggibile } from '@/composables/impostazioni-editor'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useRichiesta } from '@/composables/richiesta'

const props = defineProps<{ edizione: EdizioneCachePdf }>()
const emit = defineEmits<{ cambiata: [] }>()

const LIMITE = 50
const offset = ref(0)
const file = useRichiesta(() =>
  api.get<Pagina<FilePdf>>('/impostazioni/cache-pdf/file', { edizione_id: props.edizione.id, limit: LIMITE, offset: offset.value }),
)
watch([offset, () => props.edizione.pdf_in_cache], file.esegui, { immediate: true })

const azione = useSalvataggio()
async function elimina(f: FilePdf): Promise<void> {
  if (await azione.esegui(() => api.delete(`/impostazioni/cache-pdf/file/${f.id}`).then(() => true), 'PDF eliminato dalla cache.')) {
    emit('cambiata')
  }
}
async function invalida(): Promise<void> {
  const n = props.edizione.pdf_in_cache
  if (!(await conferma(`Eliminare tutti i ${n} PDF dalla cache per ${props.edizione.nome}?`, { testoConferma: 'Invalida', pericolosa: true }))) return
  const r = await azione.esegui(() => api.post<{ detail: string }>('/impostazioni/cache-pdf/invalida', { edizione_id: props.edizione.id }))
  if (r) {
    azione.errori.value = {}
    emit('cambiata')
  }
}
</script>

<template>
  <section class="card mb-6" :aria-labelledby="`cache-${edizione.id}`">
    <div class="card-body">
      <div class="d-flex flex-wrap align-items-center gap-3 mb-4">
        <h2 :id="`cache-${edizione.id}`" class="h6 mb-0"><IconaBs nome="archive" class="me-2" />{{ edizione.nome }}</h2>
        <span class="badge theme-secondary">{{ edizione.pdf_in_cache }} PDF</span>
        <span v-if="edizione.generazione_in_corso" class="badge theme-warning">
          <IconaBs nome="hourglass-split" class="me-1" />generazione in corso
        </span>
        <button type="button" class="btn btn-outline btn-sm theme-danger ms-auto" :disabled="azione.inCorso.value" @click="invalida">
          <IconaBs nome="trash" class="me-1" />Invalida tutti
        </button>
      </div>
      <StatoCaricamento :in-corso="file.inCorso.value && !file.dati.value" :errore="file.errore.value" @riprova="file.esegui">
        <div class="table-responsive">
          <table class="table align-middle mb-0">
            <thead>
              <tr>
                <th scope="col">Squadriglia</th>
                <th scope="col">Nome file</th>
                <th scope="col">Dimensione</th>
                <th scope="col">Caricato</th>
                <th scope="col"><span class="visually-hidden">Azioni</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in file.dati.value?.items" :key="f.id">
                <td class="small">{{ f.squadriglia || '—' }}</td>
                <td class="small fg-2 text-break">{{ f.nome || '—' }}</td>
                <td class="small fg-2 text-nowrap">{{ dimensioneLeggibile(f.dimensione) }}</td>
                <td class="small fg-2 text-nowrap">{{ dataOra(f.caricato_at) }}</td>
                <td class="text-end text-nowrap">
                  <button
                    type="button"
                    class="btn btn-outline btn-sm theme-danger"
                    :disabled="azione.inCorso.value"
                    :aria-label="`Elimina dalla cache il PDF di ${f.squadriglia ?? f.nome}`"
                    title="Elimina dalla cache"
                    @click="elimina(f)"
                  >
                    <IconaBs nome="trash" />
                  </button>
                  <a
                    v-if="f.url_esterno"
                    :href="f.url_esterno"
                    target="_blank"
                    rel="noopener"
                    class="btn btn-outline btn-sm theme-secondary ms-2"
                    :aria-label="`Apri su Drive il PDF di ${f.squadriglia ?? f.nome}`"
                    title="Apri su Drive"
                  >
                    <IconaBs nome="box-arrow-up-right" />
                  </a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <PaginazioneElenco v-model:offset="offset" :totale="file.dati.value?.count ?? 0" :limite="LIMITE" />
      </StatoCaricamento>
    </div>
  </section>
</template>
