<script setup lang="ts">
/** Concessione di una dilazione al diario (staff, prima dell'invio): `POST /edizioni/{id}/dilazioni`. */
import { ref, watch } from 'vue'

import { api, ErroreApi, type ErroriCampo } from '@/api/http'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import type { DiarioDettaglio } from '@/components/diari/diari'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ diario: DiarioDettaglio }>()
const aperta = defineModel<boolean>('aperta', { default: false })
const emit = defineEmits<{ concessa: [] }>()
const avvisi = useAvvisiStore()

const nuovaScadenza = ref('')
const motivazione = ref('')
const errori = ref<ErroriCampo>({})
const errore = ref('')
const inCorso = ref(false)

watch(aperta, () => {
  nuovaScadenza.value = props.diario.scadenza ?? ''
  motivazione.value = ''
  errori.value = {}
  errore.value = ''
})

async function concedi(): Promise<void> {
  errori.value = {}
  errore.value = ''
  if (!nuovaScadenza.value) {
    errori.value = { nuova_scadenza: ['Indica la nuova scadenza.'] }
    return
  }
  inCorso.value = true
  try {
    await api.post(`/edizioni/${props.diario.edizione_id}/dilazioni`, {
      diario_id: props.diario.id,
      nuova_scadenza: nuovaScadenza.value,
      motivazione: motivazione.value,
    })
    avvisi.mostra('Dilazione concessa.')
    aperta.value = false
    emit('concessa')
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = e.errori
      if (!Object.keys(e.errori).length) errore.value = e.message
    } else {
      errore.value = 'Operazione non riuscita.'
    }
  } finally {
    inCorso.value = false
  }
}
</script>

<template>
  <FinestraDialogo v-model:aperta="aperta" :titolo="`Dilazione — ${diario.squadriglia}`">
    <form id="form-dilazione" novalidate @submit.prevent="concedi">
      <div v-if="errore" class="alert theme-danger" role="alert">{{ errore }}</div>
      <div class="mb-5">
        <label for="dilazione-scadenza" class="form-label">Nuova scadenza</label>
        <input
          id="dilazione-scadenza"
          v-model="nuovaScadenza"
          type="date"
          class="form-control"
          :class="{ 'is-invalid': errori.nuova_scadenza?.length }"
          required
        />
        <div v-for="e in errori.nuova_scadenza ?? []" :key="e" class="invalid-feedback d-block">
          {{ e }}
        </div>
      </div>
      <div class="mb-0">
        <label for="dilazione-motivazione" class="form-label">Motivazione</label>
        <textarea
          id="dilazione-motivazione"
          v-model="motivazione"
          class="form-control"
          :class="{ 'is-invalid': errori.motivazione?.length }"
          rows="3"
        />
        <div v-for="e in errori.motivazione ?? []" :key="e" class="invalid-feedback d-block">
          {{ e }}
        </div>
      </div>
    </form>
    <template #piede>
      <button type="button" class="btn btn-outline theme-secondary" @click="aperta = false">
        Annulla
      </button>
      <button
        type="submit"
        form="form-dilazione"
        class="btn btn-solid theme-primary"
        :disabled="inCorso"
      >
        <span v-if="inCorso" class="spinner-border spinner-sm me-2" aria-hidden="true" />Concedi
        dilazione
      </button>
    </template>
  </FinestraDialogo>
</template>
