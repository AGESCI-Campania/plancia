<script setup lang="ts">
// Foto del diario, divise per modulo (1ª impresa, 2ª impresa, missione).
import { onMounted } from 'vue'

import BadgeStato from '@/components/BadgeStato.vue'
import GalleriaFoto from '@/components/moduli/GalleriaFoto.vue'
import NavigazioneModuli from '@/components/moduli/NavigazioneModuli.vue'
import { MODULI_FOTO } from '@/components/moduli/elenco'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { useDiarioCompilazione } from '@/composables/diarioCompilazione'

const props = defineProps<{ id: string }>()
const { diario, opzioni, errore, inCorso, carica, aggiorna } = useDiarioCompilazione(props.id)
onMounted(carica)
</script>

<template>
  <header class="mb-5">
    <h1 class="h3 mb-1">Foto del diario</h1>
    <p v-if="diario" class="mb-0 d-flex flex-wrap align-items-center gap-2">
      <RouterLink :to="`/diari/${diario.id}`" class="fw-semibold">Squadriglia {{ diario.squadriglia }}</RouterLink>
      <span class="fg-2">{{ diario.reparto }} · {{ diario.gruppo }} · Edizione {{ diario.edizione_anno }}</span>
      <BadgeStato :stato="diario.stato" :etichetta="diario.stato_display" />
    </p>
  </header>
  <NavigazioneModuli v-if="diario" :diario="diario" attivo="allegati" />
  <StatoCaricamento :in-corso="inCorso && !diario" :errore="errore" @riprova="carica">
    <template v-if="diario">
      <p v-if="!diario.permessi?.puo_caricare_allegati" class="fg-2">
        Nello stato attuale del diario non puoi aggiungere foto.
      </p>
      <GalleriaFoto
        v-for="m in MODULI_FOTO"
        :key="m.valore"
        class="mb-7"
        :livello="2"
        :diario-id="id"
        :modulo="m.valore"
        :titolo="m.etichetta"
        :puo-caricare="Boolean(diario.permessi?.puo_caricare_allegati)"
        :puo-eliminare="Boolean(diario.permessi?.puo_eliminare_allegati)"
        :max-px="opzioni?.allegati_max_px"
        :max-mb="opzioni?.allegati_max_mb"
        :tipi="opzioni?.allegati_tipi"
        @modificata="aggiorna()"
      />
      <RouterLink :to="`/diari/${id}`" class="btn btn-outline theme-secondary">Torna al diario</RouterLink>
    </template>
  </StatoCaricamento>
</template>
