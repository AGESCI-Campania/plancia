<script setup lang="ts">
/** Elenco delle edizioni (`GET /edizioni`): schede con stato, scadenze, evento e azioni. */
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/http'
import type { Edizione } from '@/api/tipi-edizioni'
import BadgeStato from '@/components/BadgeStato.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { formatoData, periodoEvento } from '@/composables/edizioni'
import { useRichiesta } from '@/composables/richiesta'
import { useSessioneStore } from '@/stores/sessione'

const sessione = useSessioneStore()
const edizioni = useRichiesta(() => api.get<Edizione[]>('/edizioni'))
onMounted(edizioni.esegui)
</script>

<template>
  <div class="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-6">
    <h1 class="h3 mb-0">Edizioni</h1>
    <RouterLink v-if="sessione.puo('puo_gestire_edizioni')" to="/edizioni/nuova" class="btn btn-solid theme-primary">
      <IconaBs nome="plus-lg" class="me-1" />Nuova edizione
    </RouterLink>
  </div>

  <StatoCaricamento
    :in-corso="edizioni.inCorso.value"
    :errore="edizioni.errore.value"
    :vuoto="!edizioni.dati.value?.length"
    messaggio-vuoto="Nessuna edizione presente."
    @riprova="edizioni.esegui"
  >
    <div class="row g-4">
      <div v-for="e in edizioni.dati.value ?? []" :key="e.id" class="col-12 md:col-6 lg:col-4">
        <article class="card h-100">
          <div class="card-body">
            <h2 class="h5 card-title">Guidoncini Verdi {{ e.anno }}</h2>
            <BadgeStato :stato="e.stato" :etichetta="e.stato_display" />
            <ul class="list-unstyled mt-4 mb-0 small fg-2">
              <li v-if="e.scadenza_evento"><IconaBs nome="calendar-event" class="me-2" />1ª scadenza: {{ formatoData(e.scadenza_evento) }}</li>
              <li v-if="e.scadenza_assemblea"><IconaBs nome="calendar-event" class="me-2" />2ª scadenza: {{ formatoData(e.scadenza_assemblea) }}</li>
              <li v-if="e.data_evento_inizio"><IconaBs nome="flag" class="me-2" />Evento: {{ periodoEvento(e) }}</li>
              <li v-if="e.evento_comune">
                <IconaBs nome="geo-alt" class="me-2" />{{ e.evento_comune }}<template v-if="e.evento_localita">, {{ e.evento_localita }}</template>
              </li>
            </ul>
          </div>
          <div class="card-footer flex-row gap-2">
            <RouterLink :to="`/edizioni/${e.id}`" class="btn btn-outline btn-sm theme-primary" :aria-label="`Apri l'edizione ${e.anno}`">
              Apri
            </RouterLink>
            <RouterLink
              v-if="sessione.puo('puo_gestire_edizioni')"
              :to="`/edizioni/${e.id}/modifica`"
              class="btn btn-outline btn-sm theme-secondary"
              :aria-label="`Modifica l'edizione ${e.anno}`"
            >
              Modifica
            </RouterLink>
          </div>
        </article>
      </div>
    </div>
  </StatoCaricamento>
</template>
