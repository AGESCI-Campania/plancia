<script setup lang="ts">
/**
 * Involucro standard delle pagine che caricano dati: spinner, errore con "Riprova",
 * contenuto quando pronto. `vuoto` mostra il messaggio al posto del contenuto.
 */
defineProps<{
  inCorso: boolean
  errore?: string
  vuoto?: boolean
  messaggioVuoto?: string
}>()
defineEmits<{ riprova: [] }>()
</script>

<template>
  <div v-if="inCorso" class="py-7 text-center" role="status">
    <span class="spinner-border" aria-hidden="true" /><span class="visually-hidden">Caricamento…</span>
  </div>
  <div v-else-if="errore" class="alert theme-danger d-flex align-items-center gap-3" role="alert">
    <span>{{ errore }}</span>
    <button type="button" class="btn btn-outline btn-sm theme-danger ms-auto" @click="$emit('riprova')">
      Riprova
    </button>
  </div>
  <p v-else-if="vuoto" class="fg-2 py-5">{{ messaggioVuoto ?? 'Nessun elemento.' }}</p>
  <slot v-else />
</template>
