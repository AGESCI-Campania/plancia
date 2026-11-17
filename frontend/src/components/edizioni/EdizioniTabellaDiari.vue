<script setup lang="ts">
/**
 * Diari dell'edizione visibili all'utente (`GET /diari?edizione_id=`), con i filtri della
 * pagina Django (ricerca referenti, zona, gruppo, specialità, stato, tipo, righe per
 * pagina), ordinamento per colonna e paginazione lato server.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroreApi, type Pagina } from '@/api/http'
import type { DiarioRiga, FiltriDiari } from '@/api/tipi-edizioni'
import BadgeStato from '@/components/BadgeStato.vue'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { direzioneOrdinamento, ordinamentoSuccessivo } from '@/composables/edizioni'
import { scaricaESalva } from '@/composables/file'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ edizioneId: number; mostraValutazione?: boolean }>()
/** Filtro per stato, condiviso con i contatori del riepilogo. */
const stato = defineModel<string>('stato', { default: '' })

const avvisi = useAvvisiStore()
const PER_PAGINA = [5, 10, 25, 50, 100, 200]
const TUTTI = 10000

const q = ref('')
const zona = ref('')
const gruppo = ref('')
const specialita = ref('')
const tipo = ref('')
const limite = ref(25)
const offset = ref(0)
const ordina = ref('')

const filtri = useRichiesta(() =>
  api.get<FiltriDiari>('/diari/filtri', { edizione_id: props.edizioneId }),
)
const elenco = useRichiesta(() =>
  api.get<Pagina<DiarioRiga>>('/diari', {
    edizione_id: props.edizioneId,
    q: q.value.trim(),
    zona_id: zona.value,
    gruppo_id: gruppo.value,
    specialita: specialita.value,
    stato: stato.value,
    tipo: tipo.value,
    ordina: ordina.value,
    limit: limite.value,
    offset: offset.value,
  }),
)
const righe = computed(() => elenco.dati.value?.items ?? [])
const totale = computed(() => elenco.dati.value?.count ?? 0)
const filtriAttivi = computed(() =>
  Boolean(q.value || zona.value || gruppo.value || specialita.value || stato.value || tipo.value),
)
// Con pochi diari (il Capo Squadriglia ne vede uno) i filtri sono solo rumore: compaiono
// quando l'elenco senza filtri supera la pagina più piccola.
const totaleSenzaFiltri = ref<number | null>(null)
watch(
  () => elenco.dati.value,
  (dati) => {
    if (dati && !filtriAttivi.value) totaleSenzaFiltri.value = dati.count
  },
)
const mostraFiltri = computed(() => filtriAttivi.value || (totaleSenzaFiltri.value ?? 0) > PER_PAGINA[0]!)

onMounted(() => {
  void filtri.esegui()
  void elenco.esegui()
})

// I filtri riportano alla prima pagina; la ricerca testuale aspetta che si smetta di scrivere.
let attesa: ReturnType<typeof setTimeout> | undefined
watch(q, () => {
  clearTimeout(attesa)
  attesa = setTimeout(ricarica, 300)
})
onBeforeUnmount(() => clearTimeout(attesa))
watch([zona, gruppo, specialita, stato, tipo, limite, ordina], ricarica)
watch(offset, () => void elenco.esegui())
watch(
  () => props.edizioneId,
  () => {
    totaleSenzaFiltri.value = null
    void filtri.esegui()
    ricarica()
  },
)

function ricarica(): void {
  if (offset.value !== 0) offset.value = 0 // il watch su offset ricarica
  else void elenco.esegui()
}

function azzera(): void {
  q.value = zona.value = gruppo.value = specialita.value = stato.value = tipo.value = ''
}

function ordinaPer(campo: string): void {
  ordina.value = ordinamentoSuccessivo(ordina.value, campo)
}

const referente = (r: DiarioRiga['csq']) => (r ? `${r.cognome} ${r.nome}` : '—')

const scaricando = ref<number | null>(null)
async function scaricaPdf(d: DiarioRiga): Promise<void> {
  scaricando.value = d.id
  try {
    await scaricaESalva(`/api/v1/diari/${d.id}/pdf`)
  } catch (e) {
    // 202 (PDF in preparazione) arriva come JSON: il messaggio spiega lo stato
    const corpo = e instanceof ErroreApi ? (e.corpo as { messaggio?: string } | null) : null
    avvisi.mostra(corpo?.messaggio ?? (e instanceof Error ? e.message : 'PDF non disponibile.'), 'warning')
  } finally {
    scaricando.value = null
  }
}

/** Stati in cui il diario è stato inviato allo staff (la valutazione ha senso). */
const STATI_DOPO_INVIO = new Set([
  'inviato', 'in_valutazione', 'in_revisione', 'approvato', 'non_approvato', 'maggiori_info',
])

const COLONNE = [
  { campo: 'squadriglia', etichetta: 'Squadriglia', classe: '' },
  { campo: 'reparto', etichetta: 'Reparto', classe: 'd-none md:d-table-cell' },
  { campo: 'tipo', etichetta: 'Tipo', classe: 'd-none lg:d-table-cell' },
  { campo: 'stato', etichetta: 'Stato', classe: '' },
  { campo: 'csq', etichetta: 'Capo Squadriglia', classe: 'd-none lg:d-table-cell' },
  { campo: 'crp', etichetta: 'Capo Reparto', classe: 'd-none lg:d-table-cell' },
]
</script>

<template>
  <section aria-labelledby="titolo-diari">
    <h2 id="titolo-diari" class="h4 mb-4">Diari di bordo</h2>

    <form v-if="mostraFiltri" class="row g-3 mb-5 align-items-end" role="search" aria-label="Filtri dei diari" @submit.prevent>
      <div class="col-12 md:col-4">
        <label for="diari-cerca" class="form-label d-block small fw-semibold">Cerca Capo Reparto / Capo Squadriglia</label>
        <input id="diari-cerca" v-model="q" type="search" class="form-control form-control-sm" placeholder="Cognome o nome…" autocomplete="off" />
      </div>
      <div class="col-6 md:col-2">
        <label for="diari-zona" class="form-label d-block small fw-semibold">Zona</label>
        <select id="diari-zona" v-model="zona" class="form-control form-control-sm">
          <option value="">Tutte</option>
          <option v-for="z in filtri.dati.value?.zone ?? []" :key="z.id" :value="String(z.id)">{{ z.nome }}</option>
        </select>
      </div>
      <div class="col-6 md:col-2">
        <label for="diari-gruppo" class="form-label d-block small fw-semibold">Gruppo</label>
        <select id="diari-gruppo" v-model="gruppo" class="form-control form-control-sm">
          <option value="">Tutti</option>
          <option v-for="g in filtri.dati.value?.gruppi ?? []" :key="g.id" :value="String(g.id)">{{ g.nome }}</option>
        </select>
      </div>
      <div class="col-6 md:col-2">
        <label for="diari-specialita" class="form-label d-block small fw-semibold">Specialità</label>
        <select id="diari-specialita" v-model="specialita" class="form-control form-control-sm">
          <option value="">Tutte</option>
          <option v-for="s in filtri.dati.value?.specialita ?? []" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div class="col-6 md:col-2">
        <label for="diari-stato" class="form-label d-block small fw-semibold">Stato</label>
        <select id="diari-stato" v-model="stato" class="form-control form-control-sm">
          <option value="">Tutti</option>
          <option v-for="s in filtri.dati.value?.stati ?? []" :key="s.valore" :value="s.valore">{{ s.etichetta }}</option>
        </select>
      </div>
      <div class="col-6 md:col-2">
        <label for="diari-tipo" class="form-label d-block small fw-semibold">Tipo</label>
        <select id="diari-tipo" v-model="tipo" class="form-control form-control-sm">
          <option value="">Tutti</option>
          <option v-for="t in filtri.dati.value?.tipi ?? []" :key="t.valore" :value="t.valore">{{ t.etichetta }}</option>
        </select>
      </div>
      <div class="col-6 md:col-2">
        <label for="diari-per-pagina" class="form-label d-block small fw-semibold">Per pagina</label>
        <select id="diari-per-pagina" v-model.number="limite" class="form-control form-control-sm">
          <option v-for="n in PER_PAGINA" :key="n" :value="n">{{ n }}</option>
          <option :value="TUTTI">Tutti</option>
        </select>
      </div>
      <div class="col-6 md:col-2">
        <button type="button" class="btn btn-outline btn-sm theme-secondary w-100" :disabled="!filtriAttivi" @click="azzera">
          <IconaBs nome="x-circle" class="me-1" />Azzera filtri
        </button>
      </div>
    </form>

    <StatoCaricamento
      :in-corso="elenco.inCorso.value && !elenco.dati.value"
      :errore="elenco.errore.value"
      :vuoto="!righe.length"
      :messaggio-vuoto="filtriAttivi ? 'Nessun diario corrisponde ai filtri selezionati.' : 'Nessun diario visibile per questa edizione.'"
      @riprova="elenco.esegui"
    >
      <div class="table-responsive" :aria-busy="elenco.inCorso.value">
        <table class="table table-hover align-middle">
          <caption class="visually-hidden">Diari dell'edizione</caption>
          <thead>
            <tr>
              <th
                v-for="c in COLONNE"
                :key="c.campo"
                scope="col"
                :class="c.classe"
                :aria-sort="direzioneOrdinamento(ordina, c.campo)"
              >
                <button type="button" class="btn btn-text btn-sm p-0 fw-semibold text-nowrap" @click="ordinaPer(c.campo)">
                  {{ c.etichetta }}
                  <IconaBs
                    :nome="direzioneOrdinamento(ordina, c.campo) === 'ascending' ? 'chevron-up' : direzioneOrdinamento(ordina, c.campo) === 'descending' ? 'chevron-down' : 'chevron-expand'"
                    class="ms-1 fg-2"
                  />
                </button>
              </th>
              <th scope="col"><span class="visually-hidden">Azioni</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in righe" :key="d.id">
              <td>
                <RouterLink :to="`/diari/${d.id}`" class="fw-semibold">{{ d.squadriglia }}</RouterLink>
                <small v-if="d.specialita" class="d-block fg-2">{{ d.specialita }}</small>
                <small class="d-block fg-2 md:d-none">{{ d.reparto }} · {{ d.gruppo }}</small>
              </td>
              <td class="d-none md:d-table-cell">
                {{ d.reparto }}
                <small class="d-block fg-2">{{ d.zona }} · {{ d.gruppo }}</small>
              </td>
              <td class="d-none lg:d-table-cell"><span class="badge theme-secondary">{{ d.tipo_display }}</span></td>
              <td><BadgeStato :stato="d.stato" :etichetta="d.stato_display" /></td>
              <td class="d-none lg:d-table-cell">{{ referente(d.csq) }}</td>
              <td class="d-none lg:d-table-cell">{{ referente(d.crp) }}</td>
              <td class="text-end text-nowrap">
                <RouterLink :to="`/diari/${d.id}`" class="btn btn-outline btn-sm theme-primary" :aria-label="`Apri il diario ${d.squadriglia}`" title="Apri diario">
                  <IconaBs nome="folder2-open" />
                </RouterLink>
                <RouterLink
                  v-if="mostraValutazione && STATI_DOPO_INVIO.has(d.stato)"
                  :to="`/diari/${d.id}/valutazione`"
                  class="btn btn-outline btn-sm theme-secondary ms-1"
                  :aria-label="`Valutazione del diario ${d.squadriglia}`"
                  title="Valutazione"
                >
                  <IconaBs nome="clipboard-check" />
                </RouterLink>
                <button
                  v-if="d.puo_pdf"
                  type="button"
                  class="btn btn-outline btn-sm theme-secondary ms-1"
                  :disabled="scaricando === d.id"
                  :aria-label="`Scarica il PDF del diario ${d.squadriglia}`"
                  title="Scarica PDF"
                  @click="scaricaPdf(d)"
                >
                  <IconaBs nome="file-earmark-pdf" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginazioneElenco v-if="limite !== TUTTI" v-model:offset="offset" :totale="totale" :limite="limite" />
      <p v-else-if="totale > 1" class="small fg-2">{{ totale }} diari</p>
    </StatoCaricamento>
  </section>
</template>
