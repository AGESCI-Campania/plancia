<script setup lang="ts">
/**
 * Campo di un modulo del diario: testo, area di testo (con contatore vicino al limite), data,
 * email, telefono, link o scelta; etichetta, aiuto, errori del server, sola lettura.
 */
import { computed, useId } from 'vue'

const valore = defineModel<string | null | undefined>({ default: '' })
const props = withDefaults(
  defineProps<{
    etichetta: string
    tipo?: 'text' | 'email' | 'tel' | 'url' | 'date' | 'textarea' | 'select'
    opzioni?: { valore: string; etichetta: string }[]
    /** Voce vuota in testa alla scelta (es. "— Scegli —"). */
    vuota?: string
    maxlength?: number
    righe?: number
    aiuto?: string
    segnaposto?: string
    errori?: string[]
    solaLettura?: boolean
    /** Testo del badge accanto all'etichetta (es. "solo staff"). */
    badge?: string
    autocomplete?: string
    etichettaNascosta?: boolean
  }>(),
  {
    tipo: 'text',
    opzioni: () => [],
    vuota: undefined,
    maxlength: undefined,
    righe: 4,
    aiuto: '',
    segnaposto: '',
    errori: () => [],
    solaLettura: false,
    badge: '',
    autocomplete: 'off',
    etichettaNascosta: false,
  },
)
const id = useId()

const testo = computed({
  get: () => valore.value ?? '',
  // Le date vuote vanno al server come null
  set: (v: string) => (valore.value = props.tipo === 'date' && v === '' ? null : v),
})
const lunghezza = computed(() => (valore.value ?? '').length)
const mostraContatore = computed(
  () => props.maxlength !== undefined && !props.solaLettura && lunghezza.value >= props.maxlength * 0.8,
)
const descrittori = computed(
  () => [props.aiuto ? `${id}-aiuto` : '', props.errori.length ? `${id}-errori` : ''].filter(Boolean).join(' ') || undefined,
)
</script>

<template>
  <div class="form-field">
    <label :for="id" class="form-label" :class="{ 'visually-hidden': etichettaNascosta }">
      {{ etichetta }}
      <span v-if="badge" class="badge theme-secondary ms-1 fw-normal">{{ badge }}</span>
    </label>
    <textarea
      v-if="tipo === 'textarea'"
      :id="id"
      v-model="testo"
      class="form-control"
      :class="{ 'is-invalid': errori.length }"
      :rows="righe"
      :maxlength="maxlength"
      :placeholder="segnaposto || undefined"
      :readonly="solaLettura"
      :aria-invalid="errori.length ? 'true' : undefined"
      :aria-describedby="descrittori"
    />
    <select
      v-else-if="tipo === 'select'"
      :id="id"
      v-model="testo"
      class="form-control"
      :class="{ 'is-invalid': errori.length }"
      :disabled="solaLettura"
      :aria-invalid="errori.length ? 'true' : undefined"
      :aria-describedby="descrittori"
    >
      <option v-if="vuota !== undefined" value="">{{ vuota }}</option>
      <!-- Valore salvato non più tra le scelte: resta visibile invece di sparire -->
      <option v-if="testo && !opzioni.some((o) => o.valore === testo)" :value="testo">{{ testo }}</option>
      <option v-for="o in opzioni" :key="o.valore" :value="o.valore">{{ o.etichetta }}</option>
    </select>
    <input
      v-else
      :id="id"
      v-model="testo"
      :type="tipo"
      class="form-control"
      :class="{ 'is-invalid': errori.length }"
      :maxlength="maxlength"
      :placeholder="segnaposto || undefined"
      :readonly="solaLettura"
      :autocomplete="autocomplete"
      :inputmode="tipo === 'tel' ? 'tel' : tipo === 'email' ? 'email' : tipo === 'url' ? 'url' : undefined"
      :aria-invalid="errori.length ? 'true' : undefined"
      :aria-describedby="descrittori"
    />
    <div v-if="aiuto || mostraContatore" class="d-flex gap-3">
      <div v-if="aiuto" :id="`${id}-aiuto`" class="form-text">{{ aiuto }}</div>
      <div v-if="mostraContatore" class="form-text ms-auto text-nowrap" aria-live="polite">
        {{ lunghezza }} / {{ maxlength }}
      </div>
    </div>
    <div v-if="errori.length" :id="`${id}-errori`" class="invalid-feedback">
      <div v-for="e in errori" :key="e">{{ e }}</div>
    </div>
  </div>
</template>
