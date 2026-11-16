<script setup lang="ts">
/** Badge colorato del ruolo (chiave → colore, etichetta dall'API). */
import { coloreRuolo } from '@/components/utenti/formato'

defineProps<{ ruolo: { chiave: string; etichetta: string } }>()
</script>

<template>
  <span class="badge" :class="`theme-${coloreRuolo(ruolo.chiave)}`">{{ ruolo.etichetta }}</span>
</template>
