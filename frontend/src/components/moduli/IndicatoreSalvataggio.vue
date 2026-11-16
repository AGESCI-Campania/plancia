<script setup lang="ts">
/**
 * Barra in fondo alla pagina del modulo (resta visibile scorrendo): stato del salvataggio
 * automatico annunciato agli screen reader, "Salva ora", "Riprova" e "Torna al diario".
 */
import { computed } from 'vue'

import IconaBs from '@/components/IconaBs.vue'
import type { StatoSalvataggio } from '@/composables/moduloDiario'

const props = defineProps<{
  stato: StatoSalvataggio
  ultimoSalvataggio: Date | null
  inRipetizione: boolean
  solaLettura: boolean
  diarioId: number | string
}>()
defineEmits<{ salva: []; ripeti: [] }>()

const ora = (d: Date) => d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })

const descrizione = computed(() => {
  if (props.solaLettura) return { icona: 'lock', testo: 'Sola lettura', colore: 'fg-2' }
  switch (props.stato) {
    case 'da_salvare':
      return { icona: 'pencil', testo: 'Modifiche da salvare…', colore: 'fg-2' }
    case 'salvataggio':
      return { icona: 'arrow-repeat', testo: 'Salvataggio in corso…', colore: 'fg-2' }
    case 'errore':
      return {
        icona: 'exclamation-triangle-fill',
        testo: props.inRipetizione ? 'Non salvato: nuovo tentativo a breve' : 'Non salvato',
        colore: 'fg-danger',
      }
    case 'non_valido':
      return { icona: 'exclamation-circle-fill', testo: 'Correggi i campi evidenziati', colore: 'fg-danger' }
    case 'conflitto':
      return { icona: 'exclamation-octagon-fill', testo: 'Modificato altrove', colore: 'fg-danger' }
    default:
      return {
        icona: 'check-circle-fill',
        testo: props.ultimoSalvataggio ? `Salvato alle ${ora(props.ultimoSalvataggio)}` : 'Tutto salvato',
        colore: 'fg-success',
      }
  }
})
</script>

<template>
  <div class="barra-salvataggio d-flex align-items-center gap-3 flex-wrap">
    <span class="d-inline-flex align-items-center gap-2" :class="descrizione.colore" role="status" aria-live="polite">
      <IconaBs :nome="descrizione.icona" />
      <span>{{ descrizione.testo }}</span>
    </span>
    <div class="ms-auto d-flex gap-2">
      <RouterLink :to="`/diari/${diarioId}`" class="btn btn-outline theme-secondary btn-sm">
        <IconaBs nome="arrow-left" class="me-1" />Torna al diario
      </RouterLink>
      <button
        v-if="!solaLettura && stato === 'errore'"
        type="button"
        class="btn btn-solid theme-primary btn-sm"
        @click="$emit('ripeti')"
      >
        Riprova
      </button>
      <button
        v-else-if="!solaLettura && stato !== 'conflitto'"
        type="button"
        class="btn btn-solid theme-primary btn-sm"
        :disabled="stato === 'salvataggio' || stato === 'salvato'"
        @click="$emit('salva')"
      >
        Salva ora
      </button>
    </div>
  </div>
</template>

<style scoped>
.barra-salvataggio {
  position: sticky;
  bottom: 0;
  z-index: 5;
  margin-top: 2rem;
  padding: 0.75rem 1rem;
  padding-bottom: calc(0.75rem + env(safe-area-inset-bottom, 0px));
  background: var(--bg-body, #fff);
  border-top: var(--border-width, 1px) solid var(--border-color, #dee2e6);
  box-shadow: 0 -0.25rem 0.75rem rgb(0 0 0 / 6%);
}
</style>
