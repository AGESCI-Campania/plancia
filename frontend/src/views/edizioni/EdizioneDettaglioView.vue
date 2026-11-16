<script setup lang="ts">
/**
 * Dettaglio dell'edizione (`GET /edizioni/{id}/riepilogo`): riepilogo e diari visibili al
 * ruolo; per lo staff anche stato (apri / avvia valutazione / chiudi), Excel degli esiti,
 * export riassuntivo dei diari, pubblicazione degli esiti, dilazioni e Google Drive.
 */
import { computed, onMounted, ref, useId, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import type { ExportAvviato, PubblicaEsiti, RiepilogoEdizione } from '@/api/tipi-edizioni'
import BadgeStato from '@/components/BadgeStato.vue'
import EdizioniContatori from '@/components/edizioni/EdizioniContatori.vue'
import EdizioniDilazioni from '@/components/edizioni/EdizioniDilazioni.vue'
import EdizioniDrive from '@/components/edizioni/EdizioniDrive.vue'
import EdizioniTabellaDiari from '@/components/edizioni/EdizioniTabellaDiari.vue'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { conferma } from '@/composables/conferma'
import { azioneSuccessiva } from '@/composables/edizioni'
import { scaricaESalva } from '@/composables/file'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ id: number }>()
const route = useRoute()
const router = useRouter()
const avvisi = useAvvisiStore()
const idDialogo = useId()

const riepilogo = useRichiesta(() => api.get<RiepilogoEdizione>(`/edizioni/${props.id}/riepilogo`))
const r = computed(() => riepilogo.dati.value)
const edizione = computed(() => r.value?.edizione ?? null)
const prossima = computed(() => (edizione.value ? azioneSuccessiva(edizione.value.stato) : null))
const stato = ref('')
const occupato = ref('')

onMounted(() => {
  mostraEsitoDrive()
  void riepilogo.esegui()
})
watch(() => props.id, () => void riepilogo.esegui())
watch(edizione, (e) => {
  if (e) document.title = `Guidoncini Verdi ${e.anno} · Plancia`
})

/** Ritorno dalla callback OAuth di Google Drive: `?drive=ok|errore&messaggio=…`. */
function mostraEsitoDrive(): void {
  const esito = route.query.drive
  if (esito !== 'ok' && esito !== 'errore') return
  const messaggio = typeof route.query.messaggio === 'string' ? route.query.messaggio : ''
  avvisi.mostra(
    messaggio || (esito === 'ok' ? 'Account Google Drive collegato.' : 'Collegamento a Google Drive non riuscito.'),
    esito === 'ok' ? 'success' : 'danger',
    esito === 'ok' ? 5000 : 0,
  )
  const resto = { ...route.query }
  delete resto.drive
  delete resto.messaggio
  void router.replace({ query: resto })
}

async function eseguiAzione(): Promise<void> {
  const a = prossima.value
  if (!a || !(await conferma(a.conferma, { titolo: a.etichetta, testoConferma: a.etichetta }))) return
  occupato.value = 'stato'
  try {
    const e = await api.post<{ anno: number; stato_display: string }>(`/edizioni/${props.id}/azioni/${a.azione}`)
    avvisi.mostra(`Edizione ${e.anno}: ora è «${e.stato_display}».`)
    await riepilogo.esegui()
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Operazione non riuscita.', 'danger')
  } finally {
    occupato.value = ''
  }
}

async function scaricaExcel(): Promise<void> {
  occupato.value = 'excel'
  try {
    await scaricaESalva(`/api/v1/edizioni/${props.id}/esiti-excel`)
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Excel non scaricato.', 'danger')
  } finally {
    occupato.value = ''
  }
}

const FORMATI = [
  { valore: 'xlsx', etichetta: 'Excel (xlsx)' },
  { valore: 'ods', etichetta: 'Calc (ods)' },
  { valore: 'csv', etichetta: 'CSV' },
] as const

/** Export riassuntivo: file subito, oppure 202 (in preparazione, arriverà via email). */
async function esporta(formato: string): Promise<void> {
  occupato.value = 'export'
  try {
    await scaricaESalva(`/api/v1/edizioni/${props.id}/export-diari?formato=${formato}`)
  } catch (e) {
    const avviato = e instanceof ErroreApi ? (e.corpo as Partial<ExportAvviato> | null) : null
    if (avviato?.formato) avvisi.mostra(avviato.detail ?? 'Export in preparazione: arriverà via email.', 'info', 10000)
    else avvisi.mostra(e instanceof Error ? e.message : 'Export non riuscito.', 'danger')
  } finally {
    occupato.value = ''
  }
}

// --- Pubblicazione degli esiti --------------------------------------------------------
const pubblicazione = ref(false)
const scadenza = ref('')
async function pubblica(): Promise<void> {
  occupato.value = 'pubblica'
  try {
    const q = scadenza.value ? `?scadenza=${scadenza.value}` : ''
    const { pubblicati } = await api.post<PubblicaEsiti>(`/edizioni/${props.id}/pubblica-esiti${q}`)
    pubblicazione.value = false
    avvisi.mostra(pubblicati ? `Pubblicati ${pubblicati} esiti.` : 'Nessun esito confermato da pubblicare.', pubblicati ? 'success' : 'info')
    await riepilogo.esegui()
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Pubblicazione non riuscita.', 'danger')
  } finally {
    occupato.value = ''
  }
}
</script>

<template>
  <StatoCaricamento
    :in-corso="riepilogo.inCorso.value && !r"
    :errore="riepilogo.stato.value === 404 ? 'Edizione non trovata.' : riepilogo.errore.value"
    @riprova="riepilogo.esegui"
  >
    <template v-if="r && edizione">
      <div class="d-flex flex-wrap justify-content-between align-items-start gap-4 mb-6">
        <div>
          <h1 class="h3 mb-2">Guidoncini Verdi {{ edizione.anno }}</h1>
          <BadgeStato :stato="edizione.stato" :etichetta="edizione.stato_display" />
        </div>

        <div v-if="r.puo_gestire" class="d-flex flex-wrap gap-2" role="toolbar" aria-label="Azioni sull'edizione">
          <RouterLink :to="`/edizioni/${edizione.id}/modifica`" class="btn btn-outline btn-sm theme-secondary">
            <IconaBs nome="pencil" class="me-1" />Modifica
          </RouterLink>
          <button type="button" class="btn btn-outline btn-sm theme-success" :disabled="occupato === 'excel'" @click="scaricaExcel">
            <IconaBs nome="file-earmark-excel" class="me-1" />Esiti Excel
          </button>
          <div class="position-relative">
            <button
              type="button"
              class="btn btn-outline btn-sm theme-secondary"
              data-bs-toggle="menu"
              aria-expanded="false"
              :disabled="occupato === 'export'"
            >
              <span v-if="occupato === 'export'" class="spinner-border spinner-sm me-1" aria-hidden="true" />
              <IconaBs v-else nome="table" class="me-1" />Esporta diari
              <IconaBs nome="chevron-down" class="ms-1" />
            </button>
            <div class="menu shadow">
              <button v-for="f in FORMATI" :key="f.valore" type="button" class="menu-item" @click="esporta(f.valore)">
                {{ f.etichetta }}
              </button>
            </div>
          </div>
          <button
            v-if="r.puo_pubblicare_esiti"
            type="button"
            class="btn btn-outline btn-sm theme-primary"
            @click="pubblicazione = true"
          >
            <IconaBs nome="megaphone" class="me-1" />Pubblica esiti
          </button>
          <button
            v-if="prossima"
            type="button"
            class="btn btn-solid btn-sm"
            :class="`theme-${prossima.tema}`"
            :disabled="occupato === 'stato'"
            @click="eseguiAzione"
          >
            {{ prossima.etichetta }}
          </button>
        </div>
      </div>

      <EdizioniContatori :riepilogo="r" :stato-selezionato="stato" @filtra="stato = $event" />
      <EdizioniTabellaDiari v-model:stato="stato" :edizione-id="edizione.id" :mostra-valutazione="r.puo_gestire" class="mb-8" />

      <template v-if="r.puo_gestire">
        <EdizioniDilazioni :edizione-id="edizione.id" />
        <EdizioniDrive :edizione-id="edizione.id" :anno="edizione.anno" />
      </template>

      <FinestraDialogo v-model:aperta="pubblicazione" titolo="Pubblica gli esiti">
        <form :id="`${idDialogo}-pubblica`" @submit.prevent="pubblica">
          <p>
            Vengono pubblicati tutti gli esiti <strong>confermati</strong> e non ancora pubblicati: i Capi
            Reparto potranno vederli. Le proposte della Pattuglia GV ancora in revisione restano escluse
            finché un Incaricato non le conferma.
          </p>
          <fieldset>
            <legend class="form-label">Diari da pubblicare</legend>
            <div v-for="o in [{ v: '', l: 'Tutti' }, { v: 'prima', l: 'Solo 1ª scadenza' }, { v: 'seconda', l: 'Solo 2ª scadenza' }]" :key="o.v" class="form-check">
              <input :id="`${idDialogo}-s-${o.v || 'tutti'}`" v-model="scadenza" class="form-check-input" type="radio" name="scadenza" :value="o.v" />
              <label :for="`${idDialogo}-s-${o.v || 'tutti'}`" class="form-check-label">{{ o.l }}</label>
            </div>
          </fieldset>
        </form>
        <template #piede>
          <button type="button" class="btn btn-outline theme-secondary" @click="pubblicazione = false">Annulla</button>
          <button type="submit" :form="`${idDialogo}-pubblica`" class="btn btn-solid theme-primary" :disabled="occupato === 'pubblica'">
            Pubblica
          </button>
        </template>
      </FinestraDialogo>
    </template>
  </StatoCaricamento>
</template>
