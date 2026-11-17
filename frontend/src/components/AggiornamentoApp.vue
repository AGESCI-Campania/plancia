<script setup lang="ts">
/**
 * Modale "È disponibile la versione X.Y.Z" (decisione 2 del piano 3.0): rimandabile, si
 * ripresenta a ogni avvio finché la PWA non è aggiornata; prima di aggiornare invia le
 * modifiche offline in coda; offline non compare (non si potrebbe scaricare la versione).
 */
import { computed, ref, watch } from 'vue'

import FinestraDialogo from '@/components/FinestraDialogo.vue'
import { useOnline } from '@/composables/online'
import { sincronizzaCoda } from '@/offline/coda'
import { aggiornaOra, needRefresh, versioneInferiore } from '@/pwa/aggiornamento'
import { useSitoStore } from '@/stores/sito'

const sito = useSitoStore()
const versioneApp = __VERSIONE_APP__
const online = useOnline()
const rimandata = ref(false)
const inCorso = ref(false)
const errore = ref('')

const versioneNuova = computed(() =>
  versioneInferiore(versioneApp, sito.versioneServer) ? sito.versioneServer : '',
)
const daAggiornare = computed(() => needRefresh.value || versioneNuova.value !== '')
const aperta = ref(false)

watch(
  [daAggiornare, online, rimandata],
  () => {
    aperta.value = daAggiornare.value && online.value && !rimandata.value
  },
  { immediate: true },
)

async function aggiorna(): Promise<void> {
  inCorso.value = true
  errore.value = ''
  try {
    const restano = await sincronizzaCoda()
    if (restano > 0) {
      errore.value = `Ci sono ancora ${restano} modifiche da inviare: riprova quando la connessione è stabile.`
      return
    }
    await aggiornaOra()
  } finally {
    inCorso.value = false
  }
}
</script>

<template>
  <FinestraDialogo v-model:aperta="aperta" titolo="Aggiornamento disponibile" @chiusa="rimandata = true">
    <p class="mb-0">
      È disponibile
      <template v-if="versioneNuova">la versione <strong>v{{ versioneNuova }}</strong></template>
      <template v-else>una nuova versione</template>
      di Plancia (questa è la v{{ versioneApp }}). Aggiorna per avere le correzioni e le
      novità; le modifiche non ancora inviate vengono inviate prima.
    </p>
    <p v-if="errore" class="alert theme-warning mt-3 mb-0" role="alert">{{ errore }}</p>
    <template #piede>
      <button type="button" class="btn btn-outline theme-secondary" @click="aperta = false">
        Più tardi
      </button>
      <button type="button" class="btn btn-solid theme-primary" :disabled="inCorso" @click="aggiorna">
        <span v-if="inCorso" class="spinner-border spinner-sm me-2" aria-hidden="true" />Aggiorna ora
      </button>
    </template>
  </FinestraDialogo>
</template>
