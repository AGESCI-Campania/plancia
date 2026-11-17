<script setup lang="ts">
// Interruttore (switch Bootstrap 6) con etichetta e descrizione, per i campi sì/no.
import { useId } from 'vue'

const valore = defineModel<boolean>({ default: false })
defineProps<{ etichetta: string; descrizione?: string; disabilitato?: boolean }>()
const id = useId()
</script>

<template>
  <div class="form-field mb-5">
    <div class="switch">
      <input
        :id="id"
        v-model="valore"
        type="checkbox"
        role="switch"
        :disabled="disabilitato"
        :aria-describedby="descrizione ? `${id}-desc` : undefined"
      />
    </div>
    <label :for="id" class="fw-semibold">{{ etichetta }}</label>
    <div v-if="descrizione" :id="`${id}-desc`" class="form-text">{{ descrizione }}</div>
  </div>
</template>
