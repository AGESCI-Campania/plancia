<script setup lang="ts">
/**
 * Riquadri del riepilogo edizione: diari visibili, scadenze e (solo staff, se l'API li
 * restituisce) l'avanzamento dei diari per stato. Un clic su uno stato filtra la tabella.
 */
import { computed } from 'vue'

import type { RiepilogoEdizione } from '@/api/tipi-edizioni'
import IconaBs from '@/components/IconaBs.vue'
import { formatoData, periodoEvento } from '@/composables/edizioni'

const props = defineProps<{ riepilogo: RiepilogoEdizione; statoSelezionato?: string }>()
const emit = defineEmits<{ filtra: [stato: string] }>()

const COLORI: Record<string, string> = {
  non_iniziato: 'secondary',
  in_compilazione: 'info',
  relazione_finale: 'warning',
  inviato: 'primary',
  in_valutazione: 'warning',
  in_revisione: 'warning',
  approvato: 'success',
  non_approvato: 'danger',
  maggiori_info: 'secondary',
}
const colore = (stato: string) => COLORI[stato] ?? 'secondary'

const edizione = computed(() => props.riepilogo.edizione)
const stats = computed(() => props.riepilogo.stats_diari ?? null)
const luogo = computed(() =>
  [edizione.value.evento_comune, edizione.value.evento_localita].filter(Boolean).join(', '),
)
</script>

<template>
  <div class="row g-4 mb-6">
    <div class="col-6 md:col-3">
      <div class="card h-100 text-center">
        <div class="card-body">
          <div class="fs-2 fw-bold">{{ riepilogo.totale_diari }}</div>
          <small class="fg-2">diari {{ riepilogo.puo_gestire ? 'totali' : 'visibili' }}</small>
        </div>
      </div>
    </div>
    <div v-if="edizione.scadenza_evento" class="col-6 md:col-3">
      <div class="card h-100 text-center">
        <div class="card-body">
          <div class="fs-5 fw-semibold">{{ formatoData(edizione.scadenza_evento) }}</div>
          <small class="fg-2">1ª scadenza</small>
        </div>
      </div>
    </div>
    <div v-if="edizione.scadenza_assemblea" class="col-6 md:col-3">
      <div class="card h-100 text-center">
        <div class="card-body">
          <div class="fs-5 fw-semibold">{{ formatoData(edizione.scadenza_assemblea) }}</div>
          <small class="fg-2">2ª scadenza</small>
        </div>
      </div>
    </div>
    <div v-if="edizione.data_evento_inizio || luogo" class="col-6 md:col-3">
      <div class="card h-100 text-center">
        <div class="card-body">
          <div class="fs-6 fw-semibold">{{ periodoEvento(edizione) || '—' }}</div>
          <small class="fg-2">Evento<template v-if="luogo"> · {{ luogo }}</template></small>
        </div>
      </div>
    </div>
  </div>

  <section v-if="stats" class="card mb-6" aria-labelledby="titolo-avanzamento">
    <div class="card-body">
      <div class="d-flex align-items-center gap-3 mb-4">
        <IconaBs nome="bar-chart" />
        <h2 id="titolo-avanzamento" class="h5 mb-0">Avanzamento diari</h2>
        <span class="ms-auto small fg-2">{{ stats.totale }} diari totali</span>
      </div>
      <div
        v-if="stats.totale"
        class="progress-stacked mb-4"
        role="img"
        :aria-label="stats.per_stato.filter((s) => s.totale).map((s) => `${s.label}: ${s.totale}`).join(', ')"
      >
        <template v-for="s in stats.per_stato" :key="s.stato">
          <div v-if="s.totale" class="progress" :style="{ width: `${s.percentuale}%` }" :title="`${s.label}: ${s.totale}`">
            <div class="progress-bar" :class="`theme-${colore(s.stato)}`" />
          </div>
        </template>
      </div>
      <div class="plancia-contatori-stato">
        <button
          v-for="s in stats.per_stato"
          :key="s.stato"
          type="button"
          class="btn btn-outline btn-sm d-flex flex-column align-items-center py-2"
          :class="[`theme-${colore(s.stato)}`, { active: statoSelezionato === s.stato, 'opacity-50': !s.totale }]"
          :aria-pressed="statoSelezionato === s.stato"
          @click="emit('filtra', statoSelezionato === s.stato ? '' : s.stato)"
        >
          <span class="fs-5 fw-bold">{{ s.totale }}</span>
          <span class="small lh-sm">{{ s.label }}</span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.plancia-contatori-stato {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(7.5rem, 1fr));
  gap: 0.5rem;
}
.plancia-contatori-stato .btn {
  white-space: normal;
}
</style>
