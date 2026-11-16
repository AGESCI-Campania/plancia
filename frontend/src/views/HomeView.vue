<script setup lang="ts">
// Home: edizione attiva e riepiloghi per ruolo (completata in Fase 4).
import { useSessioneStore } from '@/stores/sessione'

const sessione = useSessioneStore()
</script>

<template>
  <h1 class="h3">Benvenuto, {{ sessione.me?.nome_completo }}</h1>
  <p class="fg-2">Stai operando come {{ sessione.me?.ruolo.etichetta }}.</p>
</template>
