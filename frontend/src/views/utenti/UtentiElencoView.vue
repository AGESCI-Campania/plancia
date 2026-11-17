<script setup lang="ts">
/**
 * Utenti (staff): ricerca per email o nominativo, filtro per ruolo attivo, elenco paginato.
 * I filtri stanno nella query dell'URL (il "indietro" dal dettaglio li ritrova).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api, type Pagina } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import UtentiBadgeRuolo from '@/components/utenti/UtentiBadgeRuolo.vue'
import { offsetQuery, testoQuery } from '@/components/utenti/formato'
import type { OpzioniUtenti, UtenteLista } from '@/components/utenti/tipi'
import { useRichiesta } from '@/composables/richiesta'

const LIMITE = 25
const route = useRoute()
const router = useRouter()

const q = ref(testoQuery(route.query.q))
const ruolo = ref(testoQuery(route.query.ruolo))
const offset = ref(offsetQuery(route.query.offset))

const opzioni = useRichiesta(() => api.get<OpzioniUtenti>('/utenti/opzioni'))
const elenco = useRichiesta(() =>
  api.get<Pagina<UtenteLista>>('/utenti', { q: q.value.trim(), ruolo: ruolo.value, limit: LIMITE, offset: offset.value }),
)
const puoCreare = computed(
  () =>
    Boolean(opzioni.dati.value?.ruoli_staff_creabili.length) ||
    Boolean(opzioni.dati.value?.ruoli_nominabili_da_socio.length),
)

function aggiornaUrl(): void {
  void router.replace({
    query: {
      ...(q.value.trim() ? { q: q.value.trim() } : {}),
      ...(ruolo.value ? { ruolo: ruolo.value } : {}),
      ...(offset.value ? { offset: String(offset.value) } : {}),
    },
  })
  void elenco.esegui()
}

/** Filtri cambiati: si torna alla prima pagina (il cambio di offset ricarica da sé). */
function daCapo(): void {
  if (offset.value) offset.value = 0
  else aggiornaUrl()
}

let timer: ReturnType<typeof setTimeout> | undefined
watch(q, () => {
  clearTimeout(timer)
  timer = setTimeout(daCapo, 300)
})
watch(ruolo, daCapo)
watch(offset, aggiornaUrl)

function azzera(): void {
  clearTimeout(timer)
  q.value = ''
  ruolo.value = ''
}

onMounted(() => {
  void opzioni.esegui()
  void elenco.esegui()
})
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-3 mb-6">
    <h1 class="h3 mb-0">Utenti</h1>
    <RouterLink v-if="puoCreare" to="/utenti/nuovo" class="btn btn-solid theme-primary ms-auto">
      <IconaBs nome="person-plus" class="me-2" />Nuovo utente
    </RouterLink>
  </div>

  <form class="d-flex flex-wrap align-items-end gap-4 mb-6" role="search" @submit.prevent>
    <div class="flex-grow-1" style="min-width: min(100%, 16rem)">
      <label for="utenti-q" class="form-label">Cerca</label>
      <input
        id="utenti-q"
        v-model="q"
        type="search"
        class="form-control"
        placeholder="Email, nome o cognome"
        autocomplete="off"
      />
    </div>
    <div style="min-width: min(100%, 14rem)">
      <label for="utenti-ruolo" class="form-label">Ruolo</label>
      <select id="utenti-ruolo" v-model="ruolo" class="form-control">
        <option value="">Tutti i ruoli</option>
        <option v-for="r in opzioni.dati.value?.ruoli ?? []" :key="r.chiave" :value="r.chiave">{{ r.etichetta }}</option>
      </select>
    </div>
    <div>
      <button type="button" class="btn btn-outline theme-secondary" :disabled="!q && !ruolo" @click="azzera">
        Azzera filtri
      </button>
    </div>
  </form>

  <StatoCaricamento
    :in-corso="elenco.inCorso.value && !elenco.dati.value"
    :errore="elenco.errore.value"
    :vuoto="elenco.dati.value?.count === 0"
    messaggio-vuoto="Nessun utente trovato."
    @riprova="elenco.esegui"
  >
    <div v-if="elenco.dati.value" class="table-card table-responsive" :aria-busy="elenco.inCorso.value">
      <table class="table table-hover md:table-stacked align-middle">
        <thead>
          <tr>
            <th scope="col">Nominativo</th>
            <th scope="col">Email</th>
            <th scope="col">Ruolo</th>
            <th scope="col">Gruppo · Zona</th>
            <th scope="col"><span class="visually-hidden">Azioni</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in elenco.dati.value.items" :key="u.id">
            <td data-cell="Nominativo">
              <RouterLink :to="`/utenti/${u.id}`">{{ u.nome_completo }}</RouterLink>
              <span v-if="!u.is_active" class="badge theme-danger ms-2">Disattivato</span>
            </td>
            <td data-cell="Email" class="text-break">{{ u.email }}</td>
            <td data-cell="Ruolo"><UtentiBadgeRuolo :ruolo="u.ruolo" /></td>
            <td data-cell="Gruppo · Zona">
              <template v-if="u.socio">{{ u.socio.gruppo ?? '—' }} · {{ u.socio.zona ?? '—' }}</template>
              <span v-else class="fg-2">—</span>
            </td>
            <td class="text-end">
              <RouterLink :to="`/utenti/${u.id}`" class="btn btn-outline btn-sm theme-primary">
                Dettaglio<span class="visually-hidden"> di {{ u.nome_completo }}</span>
              </RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <PaginazioneElenco v-if="elenco.dati.value" v-model:offset="offset" :totale="elenco.dati.value.count" :limite="LIMITE" />
  </StatoCaricamento>
</template>
