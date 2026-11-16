<script setup lang="ts">
// Icona di bootstrap-icons dallo sprite SVG (un solo file in cache, funziona offline).
import sprite from 'bootstrap-icons/bootstrap-icons.svg?url'

defineProps<{ nome: string; etichetta?: string }>()
</script>

<template>
  <svg
    class="icona"
    :role="etichetta ? 'img' : undefined"
    :aria-label="etichetta"
    :aria-hidden="etichetta ? undefined : 'true'"
  >
    <use :href="`${sprite}#${nome}`" />
  </svg>
</template>
