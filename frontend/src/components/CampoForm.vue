<script setup lang="ts">
// Campo di form Bootstrap 6 con etichetta, aiuto ed errori del backend.
import { useId } from 'vue'

const valore = defineModel<string>({ default: '' })
withDefaults(
  defineProps<{
    etichetta: string
    tipo?: string
    errori?: string[]
    aiuto?: string
    autocomplete?: string
    obbligatorio?: boolean
    inputmode?: 'text' | 'numeric' | 'email' | 'tel'
  }>(),
  { tipo: 'text', errori: () => [], aiuto: '', autocomplete: 'off', obbligatorio: false, inputmode: undefined },
)
const id = useId()
</script>

<template>
  <div class="mb-5">
    <label :for="id" class="form-label">{{ etichetta }}</label>
    <input
      :id="id"
      v-model="valore"
      :type="tipo"
      class="form-control"
      :class="{ 'is-invalid': errori.length }"
      :autocomplete="autocomplete"
      :required="obbligatorio"
      :inputmode="inputmode"
      :aria-describedby="aiuto ? `${id}-aiuto` : undefined"
    />
    <div v-if="aiuto" :id="`${id}-aiuto`" class="form-text">{{ aiuto }}</div>
    <div v-for="e in errori" :key="e" class="invalid-feedback">{{ e }}</div>
  </div>
</template>
