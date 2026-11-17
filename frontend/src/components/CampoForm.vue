<script setup lang="ts">
// Campo di form Bootstrap 6 con etichetta, aiuto ed errori del backend.
// I campi password hanno il pulsante per mostrarla, come il toggle del tema AGESCI.
import { computed, ref, useId } from 'vue'

import IconaBs from '@/components/IconaBs.vue'

const valore = defineModel<string>({ default: '' })
const props = withDefaults(
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
const mostra = ref(false)
const tipoInput = computed(() => (props.tipo === 'password' && mostra.value ? 'text' : props.tipo))
</script>

<template>
  <div class="mb-5">
    <label :for="id" class="form-label">{{ etichetta }}</label>
    <div :class="{ 'input-group': tipo === 'password' }">
      <input
        :id="id"
        v-model="valore"
        :type="tipoInput"
        class="form-control"
        :class="{ 'is-invalid': errori.length }"
        :autocomplete="autocomplete"
        :required="obbligatorio"
        :inputmode="inputmode"
        :aria-describedby="aiuto ? `${id}-aiuto` : undefined"
      />
      <button
        v-if="tipo === 'password'"
        type="button"
        class="btn-outline theme-secondary input-group-btn"
        :aria-pressed="mostra"
        :aria-label="mostra ? 'Nascondi password' : 'Mostra password'"
        @click="mostra = !mostra"
      >
        <IconaBs :nome="mostra ? 'eye-slash' : 'eye'" />
      </button>
    </div>
    <div v-if="aiuto" :id="`${id}-aiuto`" class="form-text">{{ aiuto }}</div>
    <div v-for="e in errori" :key="e" class="invalid-feedback">{{ e }}</div>
  </div>
</template>
