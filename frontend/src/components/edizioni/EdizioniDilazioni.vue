<script setup lang="ts">
/**
 * Dilazioni dell'edizione (staff): elenco delle proroghe concesse e concessione di una nuova
 * scadenza a un diario non ancora inviato allo staff.
 */
import { computed, onMounted, ref, useId, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroreApi, type Pagina } from '@/api/http'
import type { DiarioRiga, Dilazione } from '@/api/tipi-edizioni'
import CampoForm from '@/components/CampoForm.vue'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { formatoData, formatoDataOra } from '@/composables/edizioni'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ edizioneId: number }>()
const avvisi = useAvvisiStore()
const id = useId()
const LIMITE = 10

const offset = ref(0)
const elenco = useRichiesta(() =>
  api.get<Pagina<Dilazione>>(`/edizioni/${props.edizioneId}/dilazioni`, { limit: LIMITE, offset: offset.value }),
)
onMounted(elenco.esegui)
watch(offset, () => void elenco.esegui())

// --- Nuova dilazione ---------------------------------------------------------------
/** Stati prima dell'invio allo staff: l'API accetta la dilazione solo in questi. */
const STATI_PRIMA_INVIO = 'non_iniziato,in_compilazione,relazione_finale'
const aperta = ref(false)
const diari = useRichiesta(() =>
  api.get<Pagina<DiarioRiga>>('/diari', {
    edizione_id: props.edizioneId,
    stato: STATI_PRIMA_INVIO,
    ordina: 'squadriglia',
    limit: 1000,
  }),
)
const diarioId = ref('')
const nuovaScadenza = ref('')
const motivazione = ref('')
const errori = ref<Record<string, string[]>>({})
const errore = ref('')
const invio = ref(false)
const puoInviare = computed(() => Boolean(diarioId.value && nuovaScadenza.value && motivazione.value.trim()))

function apri(): void {
  diarioId.value = nuovaScadenza.value = motivazione.value = errore.value = ''
  errori.value = {}
  aperta.value = true
  void diari.esegui()
}

async function concedi(): Promise<void> {
  errore.value = ''
  errori.value = {}
  invio.value = true
  try {
    const d = await api.post<Dilazione>(`/edizioni/${props.edizioneId}/dilazioni`, {
      diario_id: Number(diarioId.value),
      nuova_scadenza: nuovaScadenza.value,
      motivazione: motivazione.value.trim(),
    })
    aperta.value = false
    avvisi.mostra(`Dilazione concessa a ${d.squadriglia} fino al ${formatoData(d.nuova_scadenza)}.`)
    if (offset.value) offset.value = 0
    else void elenco.esegui()
  } catch (e) {
    errore.value = e instanceof ErroreApi ? e.message : 'Dilazione non concessa.'
    errori.value = e instanceof ErroreApi ? e.errori : {}
  } finally {
    invio.value = false
  }
}
</script>

<template>
  <section class="card mb-6" aria-labelledby="titolo-dilazioni">
    <div class="card-header flex-row flex-wrap align-items-center gap-3">
      <IconaBs nome="hourglass-split" />
      <h2 id="titolo-dilazioni" class="h5 mb-0">Dilazioni</h2>
      <button type="button" class="btn btn-outline btn-sm theme-primary ms-auto" @click="apri">
        <IconaBs nome="plus-lg" class="me-1" />Concedi dilazione
      </button>
    </div>
    <div class="card-body">
      <StatoCaricamento
        :in-corso="elenco.inCorso.value && !elenco.dati.value"
        :errore="elenco.errore.value"
        :vuoto="!elenco.dati.value?.items.length"
        messaggio-vuoto="Nessuna dilazione concessa."
        @riprova="elenco.esegui"
      >
        <ul class="list-group">
          <li v-for="d in elenco.dati.value?.items ?? []" :key="d.id" class="list-group-item">
            <div class="d-flex flex-wrap gap-2 align-items-baseline">
              <RouterLink :to="`/diari/${d.diario_id}`" class="fw-semibold">{{ d.squadriglia }}</RouterLink>
              <span>fino al <strong>{{ formatoData(d.nuova_scadenza) }}</strong></span>
              <small class="fg-2 ms-auto">{{ d.concessa_da ?? '—' }} · {{ formatoDataOra(d.creata_at) }}</small>
            </div>
            <p class="small mb-0 mt-1">{{ d.motivazione }}</p>
          </li>
        </ul>
        <PaginazioneElenco v-model:offset="offset" :totale="elenco.dati.value?.count ?? 0" :limite="LIMITE" />
      </StatoCaricamento>
    </div>

    <FinestraDialogo v-model:aperta="aperta" titolo="Concedi una dilazione">
      <form :id="`${id}-form`" novalidate @submit.prevent="concedi">
        <p class="small fg-2">Solo per i diari non ancora inviati allo staff.</p>
        <div v-if="errore" class="alert theme-danger" role="alert">{{ errore }}</div>
        <div class="mb-5">
          <label :for="`${id}-diario`" class="form-label">Diario</label>
          <select :id="`${id}-diario`" v-model="diarioId" class="form-control" required :disabled="diari.inCorso.value">
            <option value="" disabled>{{ diari.inCorso.value ? 'Caricamento…' : 'Scegli il diario' }}</option>
            <option v-for="d in diari.dati.value?.items ?? []" :key="d.id" :value="String(d.id)">
              {{ d.squadriglia }} — {{ d.reparto }} ({{ d.stato_display }})
            </option>
          </select>
          <div v-if="diari.dati.value && !diari.dati.value.items.length" class="form-text">
            Nessun diario in attesa di invio in questa edizione.
          </div>
          <div v-for="e in errori.diario_id ?? []" :key="e" class="invalid-feedback d-block">{{ e }}</div>
        </div>
        <CampoForm v-model="nuovaScadenza" etichetta="Nuova scadenza" tipo="date" obbligatorio :errori="errori.nuova_scadenza" />
        <div class="mb-5">
          <label :for="`${id}-motivazione`" class="form-label">Motivazione</label>
          <textarea
            :id="`${id}-motivazione`"
            v-model="motivazione"
            class="form-control"
            :class="{ 'is-invalid': errori.motivazione?.length }"
            rows="3"
            required
          />
          <div v-for="e in errori.motivazione ?? []" :key="e" class="invalid-feedback d-block">{{ e }}</div>
        </div>
      </form>
      <template #piede>
        <button type="button" class="btn btn-outline theme-secondary" @click="aperta = false">Annulla</button>
        <button type="submit" :form="`${id}-form`" class="btn btn-solid theme-primary" :disabled="!puoInviare || invio">
          Concedi
        </button>
      </template>
    </FinestraDialogo>
  </section>
</template>
