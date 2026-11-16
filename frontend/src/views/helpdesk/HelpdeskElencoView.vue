<script setup lang="ts">
/**
 * Helpdesk: i propri ticket (tutti per Admin, Segreteria e Incaricati EG), filtro per stato,
 * elenco paginato. Il filtro sta nella query dell'URL.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api, type Pagina } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import HelpdeskBadgeStato from '@/components/helpdesk/HelpdeskBadgeStato.vue'
import { data, offsetQuery, testoQuery } from '@/components/utenti/formato'
import type { OpzioniTicket, Ticket } from '@/components/utenti/tipi'
import { useRichiesta } from '@/composables/richiesta'

const LIMITE = 25
const route = useRoute()
const router = useRouter()
const stato = ref(testoQuery(route.query.stato))
const offset = ref(offsetQuery(route.query.offset))

const opzioni = useRichiesta(() => api.get<OpzioniTicket>('/helpdesk/opzioni'))
const elenco = useRichiesta(() =>
  api.get<Pagina<Ticket>>('/helpdesk', { stato: stato.value, limit: LIMITE, offset: offset.value }),
)
const staff = computed(() => opzioni.dati.value?.staff ?? false)

function aggiorna(): void {
  void router.replace({
    query: { ...(stato.value ? { stato: stato.value } : {}), ...(offset.value ? { offset: String(offset.value) } : {}) },
  })
  void elenco.esegui()
}
watch(stato, () => {
  if (offset.value) offset.value = 0
  else aggiorna()
})
watch(offset, aggiorna)

onMounted(() => {
  void opzioni.esegui()
  void elenco.esegui()
})
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-3 mb-2">
    <h1 class="h3 mb-0">Helpdesk</h1>
    <RouterLink to="/helpdesk/nuovo" class="btn btn-solid theme-primary ms-auto">
      <IconaBs nome="plus-lg" class="me-2" />Nuovo ticket
    </RouterLink>
  </div>
  <p class="fg-2 mb-6">
    {{ staff ? 'Tutte le richieste di assistenza.' : 'Le tue richieste di assistenza alla Segreteria e agli Incaricati EG.' }}
  </p>

  <div class="d-flex flex-wrap align-items-end gap-4 mb-5">
    <div style="min-width: min(100%, 14rem)">
      <label for="helpdesk-stato" class="form-label">Stato</label>
      <select id="helpdesk-stato" v-model="stato" class="form-control">
        <option value="">Tutti gli stati</option>
        <option v-for="s in opzioni.dati.value?.stati ?? []" :key="s.chiave" :value="s.chiave">{{ s.etichetta }}</option>
      </select>
    </div>
  </div>

  <StatoCaricamento
    :in-corso="elenco.inCorso.value && !elenco.dati.value"
    :errore="elenco.errore.value"
    :vuoto="elenco.dati.value?.count === 0"
    :messaggio-vuoto="stato ? 'Nessun ticket in questo stato.' : 'Nessun ticket.'"
    @riprova="elenco.esegui"
  >
    <div v-if="elenco.dati.value" class="table-card table-responsive" :aria-busy="elenco.inCorso.value">
      <table class="table table-hover md:table-stacked align-middle">
        <thead>
          <tr>
            <th scope="col">Oggetto</th>
            <th scope="col">Categoria</th>
            <th scope="col">Aperto da</th>
            <th v-if="staff" scope="col">Assegnato a</th>
            <th scope="col">Stato</th>
            <th scope="col">Data</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in elenco.dati.value.items" :key="t.id">
            <td data-cell="Oggetto">
              <RouterLink :to="`/helpdesk/${t.id}`"><span class="fg-2">#{{ t.id }}</span> {{ t.oggetto }}</RouterLink>
              <div v-if="t.diario" class="small fg-2">{{ t.diario.squadriglia }} · {{ t.diario.edizione_anno }}</div>
            </td>
            <td data-cell="Categoria">{{ t.categoria_display }}</td>
            <td data-cell="Aperto da">{{ t.aperto_da.nome }}</td>
            <td v-if="staff" data-cell="Assegnato a">{{ t.assegnato_a?.nome ?? '—' }}</td>
            <td data-cell="Stato"><HelpdeskBadgeStato :stato="t.stato" :etichetta="t.stato_display" /></td>
            <td data-cell="Data">{{ data(t.creato_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <PaginazioneElenco v-if="elenco.dati.value" v-model:offset="offset" :totale="elenco.dati.value.count" :limite="LIMITE" />
  </StatoCaricamento>
</template>
