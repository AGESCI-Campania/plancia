<script setup lang="ts">
/** Scelta dell'esito con note (valutazione diretta, proposta, modifica). */
import { ref, useId, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    esiti: readonly { valore: string; etichetta: string }[]
    testoInvio: string
    esitoIniziale?: string | null
    noteIniziali?: string
    noteObbligatorie?: boolean
    inCorso?: boolean
    tema?: string
  }>(),
  { esitoIniziale: '', noteIniziali: '', noteObbligatorie: false, inCorso: false, tema: 'primary' },
)
const emit = defineEmits<{ invia: [dati: { esito: string; note: string }] }>()

const id = useId()
const esito = ref(props.esitoIniziale ?? '')
const note = ref(props.noteIniziali)
const errore = ref('')
watch(
  () => [props.esitoIniziale, props.noteIniziali],
  () => {
    esito.value = props.esitoIniziale ?? ''
    note.value = props.noteIniziali
  },
)

function invia(): void {
  errore.value = esito.value ? '' : "Scegli l'esito."
  if (!errore.value) emit('invia', { esito: esito.value, note: note.value.trim() })
}
</script>

<template>
  <form novalidate @submit.prevent="invia">
    <div class="mb-4">
      <label :for="`${id}-esito`" class="form-label">Esito</label>
      <select
        :id="`${id}-esito`"
        v-model="esito"
        class="form-control"
        :class="{ 'is-invalid': errore }"
        required
        :aria-describedby="errore ? `${id}-errore` : undefined"
      >
        <option value="" disabled>Scegli l'esito</option>
        <option v-for="e in esiti" :key="e.valore" :value="e.valore">{{ e.etichetta }}</option>
      </select>
      <div v-if="errore" :id="`${id}-errore`" class="invalid-feedback d-block">{{ errore }}</div>
    </div>
    <div class="mb-4">
      <label :for="`${id}-note`" class="form-label">Note{{ noteObbligatorie ? '' : ' (facoltative)' }}</label>
      <textarea :id="`${id}-note`" v-model="note" class="form-control" rows="3" :required="noteObbligatorie" />
    </div>
    <button type="submit" class="btn btn-solid btn-sm" :class="`theme-${tema}`" :disabled="inCorso">
      <span v-if="inCorso" class="spinner-border spinner-sm me-2" aria-hidden="true" />{{ testoInvio }}
    </button>
  </form>
</template>
