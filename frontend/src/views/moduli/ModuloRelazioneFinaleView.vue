<script setup lang="ts">
// Modulo 6 — Relazione finale del Capo Reparto (mai visibile al Capo Squadriglia).
import { computed } from 'vue'

import type { components } from '@/api/schema'
import IconaBs from '@/components/IconaBs.vue'
import CampoModulo from '@/components/moduli/CampoModulo.vue'
import PaginaModulo from '@/components/moduli/PaginaModulo.vue'
import { usePaginaModulo } from '@/composables/paginaModulo'

type Relazione = components['schemas']['RelazioneFinaleSchema']

const props = defineProps<{ id: string }>()
const pagina = usePaginaModulo<Relazione>(props.id, 'relazione_finale')
const { diario, modulo, solaLettura, nonVisibile } = pagina
const { dati } = modulo
// Alias non nullo per il template (usato solo dentro `v-if="dati"`)
const d = computed(() => dati.value as Relazione)

// Scelta a tre valori come il NullBooleanSelect del form web
const SCELTE_CONQUISTATA = [
  { valore: 'true', etichetta: 'Sì' },
  { valore: 'false', etichetta: 'No' },
]
const conquistata = computed<string | null | undefined>({
  get: () => {
    const v = dati.value?.specialita_conquistata
    return v === null || v === undefined ? '' : String(v)
  },
  set: (v) => {
    if (dati.value) dati.value.specialita_conquistata = v === 'true' ? true : v === 'false' ? false : null
  },
})

const SINTESI = [
  {
    campo: 'sintesi_impresa_1',
    etichetta: 'Sintesi 1ª impresa',
    segnaposto:
      'Sintesi del percorso fatto dalla Squadriglia durante la prima impresa (oggetto, tempi, luoghi, cambiamenti che ti aspettavi in fase progettuale, obiettivi raggiunti, eventuali problematiche).',
  },
  {
    campo: 'sintesi_impresa_2',
    etichetta: 'Sintesi 2ª impresa',
    segnaposto:
      'Sintesi del percorso fatto dalla Squadriglia durante la seconda impresa (oggetto, tempi, luoghi, cambiamenti che ti aspettavi in fase progettuale, obiettivi raggiunti, eventuali problematiche).',
  },
  {
    campo: 'sintesi_missione',
    etichetta: 'Sintesi missione',
    segnaposto:
      'Sintesi del percorso fatto dalla Squadriglia durante la missione (obiettivi, tempi, luoghi, cambiamenti, obiettivi raggiunti, eventuali problematiche).',
  },
  {
    campo: 'considerazioni',
    etichetta: 'Considerazioni finali',
    segnaposto:
      'Alla fine del percorso verso la specialità, le competenze acquisite hanno avuto una ricaduta concreta nella vita di squadriglia/reparto o sono rimaste fini a se stesse? Nella conquista della specialità, i membri della squadriglia hanno acquisito specialità individuali/brevetti di competenza?',
  },
] as const
</script>

<template>
  <div v-if="nonVisibile" class="alert theme-warning" role="alert">
    La relazione finale del Capo Reparto non è visibile al Capo Squadriglia.
    <RouterLink :to="`/diari/${id}`">Torna al diario</RouterLink>
  </div>
  <PaginaModulo
    v-else
    :diario-id="id"
    chiave="relazione_finale"
    :diario="diario"
    :errore-diario="pagina.errore.value"
    :in-corso-diario="pagina.inCorso.value"
    :copia-locale="pagina.copiaLocale.value"
    :modulo="modulo"
    :sola-lettura="solaLettura"
    :avviso-sola-lettura="pagina.avvisoSolaLettura.value"
    @ricarica-diario="pagina.ricaricaDiario()"
  >
    <div class="alert theme-warning d-flex align-items-center gap-2 small" role="note">
      <IconaBs nome="lock-fill" />
      Questo modulo è riservato al Capo Reparto. Non è visibile al Capo Squadriglia.
    </div>
    <template v-if="dati">
      <div class="row g-4 mb-4">
        <div v-for="s in SINTESI" :key="s.campo" class="col-12">
          <CampoModulo
            v-model="d[s.campo]"
            tipo="textarea"
            :maxlength="10000"
            :etichetta="s.etichetta"
            :segnaposto="s.segnaposto"
            :errori="modulo.erroriDi(s.campo)"
            :sola-lettura="solaLettura"
          />
        </div>
        <div class="col-12 md:col-8">
          <CampoModulo
            v-model="conquistata"
            tipo="select"
            etichetta="Ritieni che la specialità di squadriglia sia stata conquistata?"
            vuota="Non ancora deciso"
            :opzioni="SCELTE_CONQUISTATA"
            :errori="modulo.erroriDi('specialita_conquistata')"
            :sola-lettura="solaLettura"
          />
        </div>
      </div>
    </template>
  </PaginaModulo>
</template>
