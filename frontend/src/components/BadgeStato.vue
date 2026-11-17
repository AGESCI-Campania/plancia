<script setup lang="ts">
/** Badge colorato per gli stati di diari, edizioni, ticket, inviti (chiave → colore). */
import { computed } from 'vue'

const props = defineProps<{ stato: string; etichetta?: string }>()

const COLORI: Record<string, string> = {
  non_iniziato: 'secondary',
  in_compilazione: 'info',
  relazione_finale: 'info',
  inviato: 'primary',
  in_valutazione: 'warning',
  in_revisione: 'warning',
  maggiori_info: 'warning',
  approvato: 'success',
  non_approvato: 'danger',
  bozza: 'secondary',
  aperta: 'success',
  chiusa: 'secondary',
  aperto: 'info',
  in_carico: 'warning',
  chiuso: 'secondary',
  inviato_invito: 'primary',
  attivato: 'success',
  scaduto: 'danger',
}
const colore = computed(() => COLORI[props.stato] ?? 'secondary')
</script>

<template>
  <span class="badge" :class="`theme-${colore}`">{{ etichetta ?? stato.replaceAll('_', ' ') }}</span>
</template>
