<script setup lang="ts">
import { computed } from 'vue'

import FinestraDialogo from '@/components/FinestraDialogo.vue'
import { richiestaConferma } from '@/composables/conferma'

const aperta = computed({
  get: () => richiestaConferma.value !== null,
  set: (v) => {
    if (!v) chiudi(false)
  },
})

function chiudi(ok: boolean): void {
  const r = richiestaConferma.value
  richiestaConferma.value = null
  r?.risolvi(ok)
}
</script>

<template>
  <FinestraDialogo v-model:aperta="aperta" :titolo="richiestaConferma?.titolo ?? 'Conferma'">
    <p class="mb-0">{{ richiestaConferma?.messaggio }}</p>
    <template #piede>
      <button type="button" class="btn btn-outline theme-secondary" @click="chiudi(false)">Annulla</button>
      <button
        type="button"
        class="btn btn-solid"
        :class="richiestaConferma?.pericolosa ? 'theme-danger' : 'theme-primary'"
        @click="chiudi(true)"
      >
        {{ richiestaConferma?.conferma }}
      </button>
    </template>
  </FinestraDialogo>
</template>
