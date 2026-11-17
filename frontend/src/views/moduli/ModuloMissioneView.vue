<script setup lang="ts">
// Modulo 5 — Missione: titolo, data, descrizione e svolgimento, foto.
import { computed } from 'vue'

import type { components } from '@/api/schema'
import CampoModulo from '@/components/moduli/CampoModulo.vue'
import GalleriaFoto from '@/components/moduli/GalleriaFoto.vue'
import PaginaModulo from '@/components/moduli/PaginaModulo.vue'
import { usePaginaModulo } from '@/composables/paginaModulo'

type Missione = components['schemas']['MissioneSchema']

const props = defineProps<{ id: string }>()
const pagina = usePaginaModulo<Missione>(props.id, 'missione')
const { diario, opzioni, modulo, solaLettura } = pagina
const { dati } = modulo
// Alias non nullo per il template (usato solo dentro `v-if="dati"`)
const d = computed(() => dati.value as Missione)
const facoltativa = computed(() => diario.value?.stato_moduli?.missione_obbligatoria === false)
</script>

<template>
  <PaginaModulo
    :diario-id="id"
    chiave="missione"
    :diario="diario"
    :errore-diario="pagina.errore.value"
    :in-corso-diario="pagina.inCorso.value"
    :copia-locale="pagina.copiaLocale.value"
    :modulo="modulo"
    :sola-lettura="solaLettura"
    :avviso-sola-lettura="pagina.avvisoSolaLettura.value"
    @ricarica-diario="pagina.ricaricaDiario()"
  >
    <div v-if="facoltativa" class="alert theme-info" role="note">
      Per i diari di rinnovo la missione è facoltativa: compilala solo se l'avete svolta.
    </div>
    <template v-if="dati">
      <div class="row g-4 mb-6">
        <div class="col-12 md:col-8">
          <CampoModulo
            v-model="d.titolo"
            etichetta="Titolo"
            segnaposto="Titolo della missione"
            :maxlength="200"
            :errori="modulo.erroriDi('titolo')"
            :sola-lettura="solaLettura"
          />
        </div>
        <div class="col-12 md:col-4">
          <CampoModulo v-model="d.data" tipo="date" etichetta="Data" :errori="modulo.erroriDi('data')" :sola-lettura="solaLettura" />
        </div>
        <div class="col-12">
          <CampoModulo
            v-model="d.descrizione_svolgimento"
            tipo="textarea"
            :righe="6"
            :maxlength="10000"
            etichetta="Descrizione e svolgimento"
            segnaposto="Descrizione e svolgimento della Missione; che obiettivi vi sono stati dati; quali le tecniche usate; quali competenze ha richiesto la missione e come vi siete divisi i posti d'azione; eventuali problemi, ecc."
            :errori="modulo.erroriDi('descrizione_svolgimento')"
            :sola-lettura="solaLettura"
          />
        </div>
      </div>

      <GalleriaFoto
        v-if="diario"
        class="mb-4"
        :diario-id="id"
        modulo="missione"
        titolo="Foto della missione"
        :puo-caricare="Boolean(diario.permessi?.puo_caricare_allegati)"
        :puo-eliminare="Boolean(diario.permessi?.puo_eliminare_allegati)"
        :max-px="opzioni?.allegati_max_px"
        :max-mb="opzioni?.allegati_max_mb"
        :tipi="opzioni?.allegati_tipi"
        @modificata="pagina.aggiorna()"
      />
    </template>
  </PaginaModulo>
</template>
