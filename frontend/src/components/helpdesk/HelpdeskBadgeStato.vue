<script setup lang="ts">
/** Badge dello stato di un ticket (Aperto, In lavorazione, Chiuso). */
import { coloreStatoTicket } from '@/components/utenti/formato'

defineProps<{ stato: string; etichetta: string }>()
</script>

<template>
  <span class="badge" :class="`theme-${coloreStatoTicket(stato)}`">{{ etichetta }}</span>
</template>
