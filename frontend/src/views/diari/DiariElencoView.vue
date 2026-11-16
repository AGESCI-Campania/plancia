<script setup lang="ts">
/**
 * Elenco dei diari visibili (`GET /diari`, `diari_visibili` nel backend): filtri e
 * ordinamento nella query string (link condivisibili, indietro del browser), paginazione
 * lato server, tabella da lg e card sotto. Per la Pattuglia GV è "Diari assegnati".
 */
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api, type Pagina } from '@/api/http'
import BadgeStato from '@/components/BadgeStato.vue'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import {
  filtriAttivi,
  filtriDaQuery,
  filtriVuoti,
  formattaData,
  nomeReferente,
  parametriApi,
  PER_PAGINA,
  prossimoOrdinamento,
  queryDaFiltri,
  versoOrdinamento,
  type DiarioRiga,
  type FiltriDiari,
  type FiltriDisponibili,
} from '@/components/diari/diari'
import { useRichiesta } from '@/composables/richiesta'
import { useSessioneStore } from '@/stores/sessione'

const route = useRoute()
const router = useRouter()
const sessione = useSessioneStore()

const titolo = computed(() =>
  sessione.me?.ruolo.chiave === 'pgv' ? 'Diari assegnati' : 'Diari di bordo',
)

const filtri = computed<FiltriDiari>(() => filtriDaQuery(route.query))
// La ricerca testuale si applica dopo una breve pausa di digitazione
const ricerca = ref(filtri.value.q)
watch(
  () => filtri.value.q,
  (q) => {
    if (q !== ricerca.value.trim()) ricerca.value = q
  },
)
let timerRicerca: ReturnType<typeof setTimeout> | undefined
watch(ricerca, (valore) => {
  clearTimeout(timerRicerca)
  timerRicerca = setTimeout(() => {
    if (valore.trim() !== filtri.value.q) aggiorna({ q: valore })
  }, 350)
})

function aggiorna(modifiche: Partial<FiltriDiari>, mantieniPagina = false): void {
  const nuovi = { ...filtri.value, ...modifiche }
  if (!mantieniPagina) nuovi.pagina = 1
  void router.replace({ query: queryDaFiltri(nuovi) })
}

function azzera(): void {
  ricerca.value = ''
  void router.replace({
    query: queryDaFiltri({ ...filtriVuoti(), perPagina: filtri.value.perPagina }),
  })
}

// --- Valori dei filtri ---------------------------------------------------------------------
const opzioni = useRichiesta(() =>
  api.get<FiltriDisponibili>('/diari/filtri', { edizione_id: filtri.value.edizione ?? undefined }),
)
watch(
  () => filtri.value.edizione,
  () => void opzioni.esegui(),
  { immediate: true },
)

function selezionaNumero(evento: Event): number | null {
  const v = (evento.target as HTMLSelectElement).value
  return v ? Number(v) : null
}

function cambiaStato(valore: string, attivo: boolean): void {
  const stati = new Set(filtri.value.stati)
  if (attivo) stati.add(valore)
  else stati.delete(valore)
  aggiorna({ stati: [...stati] })
}

// --- Elenco ----------------------------------------------------------------------------
const elenco = useRichiesta(() => api.get<Pagina<DiarioRiga>>('/diari', parametriApi(filtri.value)))
watch(
  () => JSON.stringify(parametriApi(filtri.value)),
  () => void elenco.esegui(),
  { immediate: true },
)

const offset = computed({
  get: () => (filtri.value.pagina - 1) * filtri.value.perPagina,
  set: (v: number) => aggiorna({ pagina: Math.floor(v / filtri.value.perPagina) + 1 }, true),
})

const colonne = [
  { campo: 'squadriglia', etichetta: 'Squadriglia' },
  { campo: 'reparto', etichetta: 'Reparto' },
  { campo: 'tipo', etichetta: 'Tipo' },
  { campo: 'stato', etichetta: 'Stato' },
  { campo: 'csq', etichetta: 'Capo Squadriglia' },
  { campo: 'crp', etichetta: 'Capo Reparto' },
] as const

function ordinaPer(campo: string): void {
  aggiorna({ ordina: prossimoOrdinamento(filtri.value.ordina, campo) })
}

const ORDINAMENTI_MOBILE = [
  { valore: '', etichetta: 'Predefinito' },
  { valore: 'squadriglia', etichetta: 'Squadriglia (A-Z)' },
  { valore: '-squadriglia', etichetta: 'Squadriglia (Z-A)' },
  { valore: 'reparto', etichetta: 'Reparto' },
  { valore: 'gruppo', etichetta: 'Gruppo' },
  { valore: 'zona', etichetta: 'Zona' },
  { valore: 'stato', etichetta: 'Stato' },
  { valore: 'tipo', etichetta: 'Tipo' },
  { valore: 'csq', etichetta: 'Capo Squadriglia' },
  { valore: 'crp', etichetta: 'Capo Reparto' },
  { valore: '-aggiornato', etichetta: 'Aggiornati di recente' },
]

function apri(d: DiarioRiga): void {
  void router.push(`/diari/${d.id}`)
}

const mostraFiltri = ref(false)
const numeroFiltri = computed(() => {
  const f = filtri.value
  return (
    [f.edizione, f.zona, f.gruppo, f.reparto, f.tipo, f.specialita, f.q.trim()].filter(Boolean)
      .length + f.stati.length
  )
})
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-3 mb-6">
    <h1 class="h3 mb-0">{{ titolo }}</h1>
    <button
      type="button"
      class="btn btn-outline btn-sm theme-secondary ms-auto lg:d-none"
      :aria-expanded="mostraFiltri"
      aria-controls="diari-filtri"
      @click="mostraFiltri = !mostraFiltri"
    >
      <IconaBs nome="funnel" class="me-2" />Filtri<span
        v-if="numeroFiltri"
        class="badge theme-primary ms-2"
        >{{ numeroFiltri }}</span
      >
    </button>
  </div>

  <!-- Filtri: sempre visibili da lg, a scomparsa sotto -->
  <section
    id="diari-filtri"
    class="card mb-6"
    :class="{ 'd-none lg:d-block': !mostraFiltri }"
    aria-label="Filtri dei diari"
  >
    <div class="card-body">
      <form class="row g-5 align-items-end" role="search" @submit.prevent>
        <div class="col-12 md:col-6 xl:col-4">
          <label for="diari-q" class="form-label">Cerca</label>
          <input
            id="diari-q"
            v-model="ricerca"
            type="search"
            class="form-control"
            placeholder="Squadriglia, Capo Squadriglia o Capo Reparto…"
            autocomplete="off"
          />
        </div>
        <div class="col-6 md:col-3 xl:col-2">
          <label for="diari-edizione" class="form-label">Edizione</label>
          <select
            id="diari-edizione"
            class="form-control"
            :value="filtri.edizione ?? ''"
            @change="
              aggiorna({
                edizione: selezionaNumero($event),
                zona: null,
                gruppo: null,
                reparto: null,
                specialita: '',
              })
            "
          >
            <option value="">Tutte</option>
            <option v-for="e in opzioni.dati.value?.edizioni ?? []" :key="e.id" :value="e.id">
              {{ e.nome }}
            </option>
          </select>
        </div>
        <div class="col-6 md:col-3 xl:col-2">
          <label for="diari-zona" class="form-label">Zona</label>
          <select
            id="diari-zona"
            class="form-control"
            :value="filtri.zona ?? ''"
            @change="aggiorna({ zona: selezionaNumero($event) })"
          >
            <option value="">Tutte</option>
            <option v-for="z in opzioni.dati.value?.zone ?? []" :key="z.id" :value="z.id">
              {{ z.nome }}
            </option>
          </select>
        </div>
        <div class="col-6 md:col-4 xl:col-2">
          <label for="diari-gruppo" class="form-label">Gruppo</label>
          <select
            id="diari-gruppo"
            class="form-control"
            :value="filtri.gruppo ?? ''"
            @change="aggiorna({ gruppo: selezionaNumero($event) })"
          >
            <option value="">Tutti</option>
            <option v-for="g in opzioni.dati.value?.gruppi ?? []" :key="g.id" :value="g.id">
              {{ g.nome }}
            </option>
          </select>
        </div>
        <div class="col-6 md:col-4 xl:col-2">
          <label for="diari-reparto" class="form-label">Reparto</label>
          <select
            id="diari-reparto"
            class="form-control"
            :value="filtri.reparto ?? ''"
            @change="aggiorna({ reparto: selezionaNumero($event) })"
          >
            <option value="">Tutti</option>
            <option v-for="r in opzioni.dati.value?.reparti ?? []" :key="r.id" :value="r.id">
              {{ r.nome }}
            </option>
          </select>
        </div>
        <div class="col-6 md:col-4 xl:col-3">
          <label for="diari-specialita" class="form-label">Specialità</label>
          <select
            id="diari-specialita"
            class="form-control"
            :value="filtri.specialita"
            @change="aggiorna({ specialita: ($event.target as HTMLSelectElement).value })"
          >
            <option value="">Tutte</option>
            <option v-for="s in opzioni.dati.value?.specialita ?? []" :key="s" :value="s">
              {{ s }}
            </option>
          </select>
        </div>
        <div class="col-6 md:col-3 xl:col-2">
          <label for="diari-tipo" class="form-label">Tipo</label>
          <select
            id="diari-tipo"
            class="form-control"
            :value="filtri.tipo"
            @change="aggiorna({ tipo: ($event.target as HTMLSelectElement).value })"
          >
            <option value="">Tutti</option>
            <option v-for="t in opzioni.dati.value?.tipi ?? []" :key="t.valore" :value="t.valore">
              {{ t.etichetta }}
            </option>
          </select>
        </div>
        <div class="col-6 md:col-3 xl:col-2">
          <label for="diari-per-pagina" class="form-label">Per pagina</label>
          <select
            id="diari-per-pagina"
            class="form-control"
            :value="filtri.perPagina"
            @change="aggiorna({ perPagina: Number(($event.target as HTMLSelectElement).value) })"
          >
            <option v-for="n in PER_PAGINA" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
        <div class="col-12 md:col-6 lg:d-none">
          <label for="diari-ordina" class="form-label">Ordina per</label>
          <select
            id="diari-ordina"
            class="form-control"
            :value="filtri.ordina"
            @change="aggiorna({ ordina: ($event.target as HTMLSelectElement).value })"
          >
            <option v-for="o in ORDINAMENTI_MOBILE" :key="o.valore" :value="o.valore">
              {{ o.etichetta }}
            </option>
          </select>
        </div>
        <fieldset class="col-12">
          <legend class="form-label fs-md mb-3">Stato</legend>
          <div class="d-flex flex-wrap gap-3">
            <label
              v-for="s in opzioni.dati.value?.stati ?? []"
              :key="s.valore"
              class="btn btn-sm"
              :class="
                filtri.stati.includes(s.valore)
                  ? 'btn-solid theme-primary'
                  : 'btn-outline theme-secondary'
              "
            >
              <input
                type="checkbox"
                class="visually-hidden"
                :checked="filtri.stati.includes(s.valore)"
                @change="cambiaStato(s.valore, ($event.target as HTMLInputElement).checked)"
              />
              <IconaBs v-if="filtri.stati.includes(s.valore)" nome="check-lg" class="me-1" />{{
                s.etichetta
              }}
            </label>
          </div>
        </fieldset>
        <div v-if="filtriAttivi(filtri)" class="col-12">
          <button type="button" class="btn btn-text btn-sm theme-secondary" @click="azzera">
            <IconaBs nome="x-circle" class="me-2" />Azzera filtri
          </button>
        </div>
      </form>
    </div>
  </section>

  <StatoCaricamento
    :in-corso="elenco.inCorso.value && !elenco.dati.value"
    :errore="elenco.errore.value"
    :vuoto="elenco.dati.value?.count === 0"
    :messaggio-vuoto="
      filtriAttivi(filtri) ? 'Nessun diario corrisponde ai filtri.' : 'Nessun diario disponibile.'
    "
    @riprova="elenco.esegui"
  >
    <template v-if="elenco.dati.value">
      <p class="small fg-2 mb-3" role="status" aria-live="polite">
        {{ elenco.dati.value.count }} {{ elenco.dati.value.count === 1 ? 'diario' : 'diari' }}
        <span
          v-if="elenco.inCorso.value"
          class="spinner-border spinner-sm ms-2"
          aria-hidden="true"
        />
      </p>

      <!-- Desktop: tabella -->
      <div class="d-none lg:d-block table-card">
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <caption class="visually-hidden">
              {{
                titolo
              }}
            </caption>
            <thead>
              <tr>
                <th
                  v-for="c in colonne"
                  :key="c.campo"
                  scope="col"
                  :aria-sort="versoOrdinamento(filtri.ordina, c.campo)"
                >
                  <button
                    type="button"
                    class="btn btn-text btn-sm p-0 fw-semibold text-nowrap"
                    @click="ordinaPer(c.campo)"
                  >
                    {{ c.etichetta }}
                    <IconaBs
                      :nome="
                        versoOrdinamento(filtri.ordina, c.campo) === 'ascending'
                          ? 'sort-up'
                          : versoOrdinamento(filtri.ordina, c.campo) === 'descending'
                            ? 'sort-down'
                            : 'chevron-expand'
                      "
                      class="ms-1"
                      :class="{ 'opacity-50': versoOrdinamento(filtri.ordina, c.campo) === 'none' }"
                    />
                  </button>
                </th>
                <th scope="col">Scadenza</th>
                <th scope="col"><span class="visually-hidden">Azioni</span></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="d in elenco.dati.value.items"
                :key="d.id"
                class="plancia-diari-riga"
                @click="apri(d)"
              >
                <td>
                  <RouterLink :to="`/diari/${d.id}`" class="fw-semibold" @click.stop>{{
                    d.squadriglia
                  }}</RouterLink>
                  <div v-if="d.specialita" class="small fg-2">{{ d.specialita }}</div>
                </td>
                <td>
                  {{ d.reparto }}
                  <div class="small fg-2">{{ d.zona }} · {{ d.gruppo }}</div>
                </td>
                <td>
                  <span class="badge theme-secondary">{{ d.tipo_display }}</span>
                </td>
                <td><BadgeStato :stato="d.stato" :etichetta="d.stato_display" /></td>
                <td class="small">{{ nomeReferente(d.csq) || '—' }}</td>
                <td class="small">{{ nomeReferente(d.crp) || '—' }}</td>
                <td class="small text-nowrap">{{ formattaData(d.scadenza) || '—' }}</td>
                <td class="text-end text-nowrap">
                  <RouterLink
                    v-if="d.puo_pdf"
                    :to="`/diari/${d.id}/pdf`"
                    class="btn btn-outline btn-sm theme-secondary"
                    :title="`PDF di ${d.squadriglia}`"
                    @click.stop
                  >
                    <IconaBs nome="file-earmark-pdf" :etichetta="`PDF di ${d.squadriglia}`" />
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Mobile: card -->
      <ul class="lg:d-none list-unstyled d-grid gap-5 mb-0">
        <li v-for="d in elenco.dati.value.items" :key="d.id" class="card">
          <div class="card-body">
            <div class="d-flex align-items-start gap-3">
              <div class="flex-grow-1 min-w-0">
                <h2 class="h6 mb-1">
                  <RouterLink :to="`/diari/${d.id}`" class="stretched-link">{{
                    d.squadriglia
                  }}</RouterLink>
                </h2>
                <div class="small fg-2">{{ d.reparto }} · {{ d.gruppo }} · {{ d.zona }}</div>
              </div>
              <BadgeStato :stato="d.stato" :etichetta="d.stato_display" />
            </div>
            <dl class="row small mb-0 mt-3 g-1">
              <dt class="col-5 fw-normal fg-2">Tipo</dt>
              <dd class="col-7 mb-0">
                {{ d.tipo_display }}<template v-if="d.specialita"> · {{ d.specialita }}</template>
              </dd>
              <dt class="col-5 fw-normal fg-2">Capo Squadriglia</dt>
              <dd class="col-7 mb-0">{{ nomeReferente(d.csq) || '—' }}</dd>
              <dt class="col-5 fw-normal fg-2">Capo Reparto</dt>
              <dd class="col-7 mb-0">{{ nomeReferente(d.crp) || '—' }}</dd>
              <dt class="col-5 fw-normal fg-2">Scadenza</dt>
              <dd class="col-7 mb-0">{{ formattaData(d.scadenza) || '—' }}</dd>
            </dl>
          </div>
          <div v-if="d.puo_pdf" class="card-footer position-relative plancia-diari-sopra">
            <RouterLink :to="`/diari/${d.id}/pdf`" class="btn btn-outline btn-sm theme-secondary">
              <IconaBs nome="file-earmark-pdf" class="me-2" />PDF
            </RouterLink>
          </div>
        </li>
      </ul>

      <PaginazioneElenco
        v-model:offset="offset"
        :totale="elenco.dati.value.count"
        :limite="filtri.perPagina"
      />
    </template>
  </StatoCaricamento>
  <p v-if="opzioni.errore.value" class="small fg-danger mt-3">
    Filtri non disponibili: {{ opzioni.errore.value }}
  </p>
</template>

<style scoped>
.plancia-diari-riga {
  cursor: pointer;
}
.plancia-diari-sopra {
  z-index: 2;
}
</style>
