<script setup lang="ts">
/**
 * Home: l'edizione attiva (aperta o in valutazione più recente) con il riepilogo per il
 * ruolo, oppure la pagina informativa se non ce n'è una (`GET /edizioni/attiva`).
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/http'
import type { EdizioneAttiva } from '@/api/tipi-edizioni'
import BadgeStato from '@/components/BadgeStato.vue'
import EdizioniContatori from '@/components/edizioni/EdizioniContatori.vue'
import EdizioniTabellaDiari from '@/components/edizioni/EdizioniTabellaDiari.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { useRichiesta } from '@/composables/richiesta'
import { useSessioneStore } from '@/stores/sessione'

const sessione = useSessioneStore()
const attiva = useRichiesta(() => api.get<EdizioneAttiva>('/edizioni/attiva'))
const riepilogo = computed(() => attiva.dati.value?.riepilogo ?? null)
const stato = ref('')

onMounted(attiva.esegui)
</script>

<template>
  <div class="d-flex flex-wrap align-items-baseline gap-3 mb-6">
    <h1 class="h3 mb-0">Benvenuto, {{ sessione.me?.nome_completo }}</h1>
    <span class="fg-2">Stai operando come {{ sessione.me?.ruolo.etichetta }}.</span>
  </div>

  <StatoCaricamento :in-corso="attiva.inCorso.value" :errore="attiva.errore.value" @riprova="attiva.esegui">
    <template v-if="riepilogo">
      <div class="d-flex flex-wrap align-items-center gap-3 mb-5">
        <h2 class="h4 mb-0">Guidoncini Verdi {{ riepilogo.edizione.anno }}</h2>
        <BadgeStato :stato="riepilogo.edizione.stato" :etichetta="riepilogo.edizione.stato_display" />
        <RouterLink
          v-if="riepilogo.puo_gestire"
          :to="`/edizioni/${riepilogo.edizione.id}`"
          class="btn btn-outline btn-sm theme-primary ms-auto"
        >
          <IconaBs nome="gear" class="me-1" />Gestisci edizione
        </RouterLink>
      </div>
      <EdizioniContatori :riepilogo="riepilogo" :stato-selezionato="stato" @filtra="stato = $event" />
      <EdizioniTabellaDiari
        v-model:stato="stato"
        :edizione-id="riepilogo.edizione.id"
        :mostra-valutazione="riepilogo.puo_gestire"
      />
    </template>

    <div v-else class="card text-center">
      <div class="card-body py-10">
        <IconaBs nome="calendar-x" class="fs-1 fg-2 mb-4" />
        <h2 class="h4">Nessuna edizione attiva</h2>
        <p class="fg-2">
          Al momento non ci sono edizioni dei Guidoncini Verdi aperte o in corso di valutazione.
        </p>
        <template v-if="attiva.dati.value?.puo_gestire">
          <p class="fg-2">Puoi creare una nuova edizione o aprire un'edizione in bozza.</p>
          <div class="d-flex flex-wrap gap-3 justify-content-center">
            <RouterLink to="/edizioni" class="btn btn-outline theme-primary">Elenco edizioni</RouterLink>
            <RouterLink to="/edizioni/nuova" class="btn btn-solid theme-primary">Nuova edizione</RouterLink>
          </div>
        </template>
        <template v-else>
          <p class="fg-2">Contatta lo staff per informazioni sull'edizione corrente.</p>
          <RouterLink to="/helpdesk" class="btn btn-outline theme-primary">Apri una richiesta di supporto</RouterLink>
        </template>
      </div>
    </div>
  </StatoCaricamento>
</template>
