<script setup lang="ts">
/**
 * Nuova edizione (`POST /edizioni`) o modifica (`PATCH /edizioni/{id}`): dati generali,
 * scadenze ed evento, come `EdizioneForm`. La configurazione di Google Drive sta nel
 * dettaglio dell'edizione (lì torna anche il collegamento dell'account).
 */
import { computed, onMounted, ref, useId } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import type { Edizione } from '@/api/tipi-edizioni'
import CampoForm from '@/components/CampoForm.vue'
import EdizioniComune from '@/components/edizioni/EdizioniComune.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import {
  corpoEdizione,
  formDaEdizione,
  STATI_EDIZIONE,
  validaEdizione,
  type FormEdizione,
} from '@/composables/edizioni'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ id?: number }>()
const router = useRouter()
const avvisi = useAvvisiStore()
const idStato = useId()

const nuova = computed(() => props.id === undefined)
const caricamento = useRichiesta(() => api.get<Edizione>(`/edizioni/${props.id}`))
const form = ref<FormEdizione>(formDaEdizione(null))
const errori = ref<Record<string, string[]>>({})
const errore = ref('')
const salvataggio = ref(false)

onMounted(async () => {
  if (nuova.value) return
  const e = await caricamento.esegui()
  if (e) form.value = formDaEdizione(e)
})

const titolo = computed(() =>
  nuova.value ? 'Nuova edizione' : `Modifica edizione ${caricamento.dati.value?.anno ?? ''}`,
)

async function salva(): Promise<void> {
  errore.value = ''
  errori.value = validaEdizione(form.value)
  if (Object.keys(errori.value).length) return
  salvataggio.value = true
  try {
    const corpo = corpoEdizione(form.value)
    const e = nuova.value
      ? await api.post<Edizione>('/edizioni', corpo)
      : await api.patch<Edizione>(`/edizioni/${props.id}`, corpo)
    avvisi.mostra(nuova.value ? `Edizione ${e.anno} creata.` : `Edizione ${e.anno} salvata.`)
    await router.push(nuova.value ? '/edizioni' : `/edizioni/${e.id}`)
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = e.errori
      errore.value = e.message
    } else {
      errore.value = 'Salvataggio non riuscito.'
    }
  } finally {
    salvataggio.value = false
  }
}
</script>

<template>
  <div class="row justify-content-center">
    <div class="col-12 lg:col-9">
      <h1 class="h3 mb-6">{{ titolo }}</h1>
      <StatoCaricamento
        :in-corso="caricamento.inCorso.value"
        :errore="caricamento.errore.value"
        @riprova="caricamento.esegui"
      >
        <form novalidate @submit.prevent="salva">
          <div v-if="errore" class="alert theme-danger" role="alert">
            {{ errore }}
            <ul v-if="errori.__all__?.length" class="mb-0 mt-2">
              <li v-for="e in errori.__all__" :key="e">{{ e }}</li>
            </ul>
          </div>

          <fieldset class="card mb-6">
            <legend class="card-header fw-semibold fs-6 mb-0">Dati generali</legend>
            <div class="card-body row g-4">
              <div class="col-12 sm:col-3">
                <CampoForm v-model="form.anno" etichetta="Anno" inputmode="numeric" obbligatorio :errori="errori.anno" />
              </div>
              <div class="col-12 sm:col-9 mb-5">
                <label :for="idStato" class="form-label">Stato</label>
                <select :id="idStato" v-model="form.stato" class="form-control" :class="{ 'is-invalid': errori.stato?.length }">
                  <option v-for="s in STATI_EDIZIONE" :key="s.valore" :value="s.valore">{{ s.etichetta }}</option>
                </select>
                <div class="form-text">Di norma lo stato si cambia dal dettaglio con Apri / Avvia valutazione / Chiudi.</div>
                <div v-for="e in errori.stato ?? []" :key="e" class="invalid-feedback d-block">{{ e }}</div>
              </div>
            </div>
          </fieldset>

          <fieldset class="card mb-6">
            <legend class="card-header fw-semibold fs-6 mb-0">Scadenze</legend>
            <div class="card-body row g-4">
              <div class="col-12 sm:col-6">
                <CampoForm v-model="form.scadenza_evento" etichetta="1ª scadenza (evento)" tipo="date" :errori="errori.scadenza_evento" />
              </div>
              <div class="col-12 sm:col-6">
                <CampoForm v-model="form.scadenza_assemblea" etichetta="2ª scadenza (assemblea)" tipo="date" :errori="errori.scadenza_assemblea" />
              </div>
            </div>
          </fieldset>

          <fieldset class="card mb-6">
            <legend class="card-header fw-semibold fs-6 mb-0">Evento Guidoncini Verdi</legend>
            <div class="card-body">
              <div class="row g-4">
                <div class="col-12 sm:col-6">
                  <CampoForm v-model="form.data_evento_inizio" etichetta="Inizio evento" tipo="date" :errori="errori.data_evento_inizio" />
                </div>
                <div class="col-12 sm:col-6">
                  <CampoForm v-model="form.data_evento_fine" etichetta="Fine evento" tipo="date" :errori="errori.data_evento_fine" />
                </div>
              </div>
              <EdizioniComune v-model="form.evento_comune" :errori="errori.evento_comune" />
              <CampoForm v-model="form.evento_localita" etichetta="Località" :errori="errori.evento_localita" />
            </div>
          </fieldset>

          <div class="d-flex flex-wrap gap-3 mb-8">
            <button type="submit" class="btn btn-solid theme-primary" :disabled="salvataggio">
              <span v-if="salvataggio" class="spinner-border spinner-sm me-2" aria-hidden="true" />Salva edizione
            </button>
            <RouterLink :to="nuova ? '/edizioni' : `/edizioni/${id}`" class="btn btn-outline theme-secondary">Annulla</RouterLink>
          </div>
        </form>
      </StatoCaricamento>
    </div>
  </div>
</template>
