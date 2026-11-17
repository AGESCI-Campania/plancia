<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import CampoForm from '@/components/CampoForm.vue'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import { confermaRiautenticazione, richiestaRiautenticazione } from '@/composables/riautenticazione'

const segreto = ref('')
const errore = ref('')
const aperta = computed({
  get: () => richiestaRiautenticazione.value !== null,
  set: (valore) => {
    if (!valore) chiudi(false)
  },
})
const conCodice = computed(() => richiestaRiautenticazione.value?.conCodice ?? false)
watch(aperta, () => {
  segreto.value = ''
  errore.value = ''
})

function chiudi(ok: boolean): void {
  const richiesta = richiestaRiautenticazione.value
  richiestaRiautenticazione.value = null
  richiesta?.risolvi(ok)
}

async function conferma(): Promise<void> {
  errore.value = await confermaRiautenticazione(segreto.value, conCodice.value)
  if (!errore.value) chiudi(true)
}
</script>

<template>
  <FinestraDialogo v-model:aperta="aperta" titolo="Conferma la tua identità">
    <form id="form-riautenticazione" novalidate @submit.prevent="conferma">
      <p>Per questa operazione serve confermare di nuovo l'accesso.</p>
      <CampoForm
        v-model="segreto"
        :etichetta="conCodice ? 'Codice di verifica' : 'Password'"
        :tipo="conCodice ? 'text' : 'password'"
        :autocomplete="conCodice ? 'one-time-code' : 'current-password'"
        :errori="errore ? [errore] : []"
        obbligatorio
      />
    </form>
    <template #piede>
      <button type="button" class="btn btn-outline theme-secondary" @click="chiudi(false)">Annulla</button>
      <button type="submit" form="form-riautenticazione" class="btn btn-solid theme-primary">Conferma</button>
    </template>
  </FinestraDialogo>
</template>
