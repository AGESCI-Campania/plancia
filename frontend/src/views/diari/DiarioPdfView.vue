<script setup lang="ts">
/**
 * Viewer del PDF del diario (moduli 1–6, mai la valutazione; mai al Capo Squadriglia).
 * Chiede lo stato (`/pdf/stato`): se pronto scarica il file e lo mostra in un iframe
 * (desktop e Android) con il pulsante Scarica, che su iOS in PWA usa la condivisione;
 * se non è pronto mostra lo stato, permette di avviarne la generazione (`POST /pdf`) e
 * ricontrolla periodicamente finché non è pronto. Porta static/js/plancia-file-viewer.js.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import type { StatoPdf } from '@/components/diari/diari'
import { iosPwa, salvaFile, scaricaFile } from '@/composables/file'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ id: number }>()
const avvisi = useAvvisiStore()

const stato = ref<StatoPdf | null>(null)
const file = ref<File | null>(null)
const urlAnteprima = ref('')
const caricamento = ref(true)
const errore = ref('')
const avvio = ref(false)
const salvataggio = ref(false)
const anteprima = computed(() => Boolean(file.value) && !iosPwa())
const urlPdf = computed(() => `/api/v1/diari/${props.id}/pdf`)
let timer: ReturnType<typeof setTimeout> | undefined
let attivo = true

const INTERVALLO_MS: Record<string, number> = { in_generazione: 5000, bloccato: 15000 }

function pulisciAnteprima(): void {
  if (urlAnteprima.value) URL.revokeObjectURL(urlAnteprima.value)
  urlAnteprima.value = ''
}

function statoDaErrore(e: unknown): StatoPdf | null {
  // GET /pdf risponde 202 con lo stato in JSON se il file non è pronto
  const corpo = e instanceof ErroreApi ? (e.corpo as Partial<StatoPdf> | null) : null
  return corpo && typeof corpo.stato === 'string' ? (corpo as StatoPdf) : null
}

async function scaricaPdf(): Promise<void> {
  try {
    file.value = await scaricaFile(stato.value?.download_url ?? urlPdf.value)
    pulisciAnteprima()
    if (!iosPwa()) urlAnteprima.value = URL.createObjectURL(file.value)
  } catch (e) {
    const s = statoDaErrore(e)
    if (s) stato.value = s
    else
      errore.value =
        e instanceof ErroreApi
          ? e.message
          : 'Il file non è disponibile o si è verificato un errore.'
  }
}

function programma(): void {
  clearTimeout(timer)
  const ms = stato.value ? INTERVALLO_MS[stato.value.stato] : undefined
  if (ms && attivo) timer = setTimeout(() => void aggiorna(), ms)
}

async function aggiorna(): Promise<void> {
  errore.value = ''
  try {
    stato.value = await api.get<StatoPdf>(`/diari/${props.id}/pdf/stato`)
    if (stato.value.stato === 'pronto' && !file.value) await scaricaPdf()
  } catch (e) {
    errore.value = e instanceof ErroreApi ? e.message : 'Stato del PDF non disponibile.'
  } finally {
    caricamento.value = false
    programma()
  }
}

async function genera(): Promise<void> {
  avvio.value = true
  try {
    stato.value = await api.post<StatoPdf>(`/diari/${props.id}/pdf`)
    avvisi.mostra(stato.value.messaggio, stato.value.avviato ? 'info' : 'warning', 8000)
    if (stato.value.stato === 'pronto') await scaricaPdf()
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Generazione non avviata.', 'danger')
  } finally {
    avvio.value = false
    programma()
  }
}

async function salva(): Promise<void> {
  salvataggio.value = true
  try {
    if (file.value) await salvaFile(file.value)
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Salvataggio non riuscito.', 'danger')
  } finally {
    salvataggio.value = false
  }
}

watch(
  () => props.id,
  () => {
    file.value = null
    stato.value = null
    pulisciAnteprima()
    caricamento.value = true
    void aggiorna()
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  attivo = false
  clearTimeout(timer)
  pulisciAnteprima()
})
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-3 mb-5">
    <RouterLink :to="`/diari/${id}`" class="btn btn-outline btn-sm theme-secondary">
      <IconaBs nome="arrow-left" class="me-2" />Torna al diario
    </RouterLink>
    <h1 class="h5 mb-0 flex-grow-1 text-truncate min-w-0">{{ file?.name ?? 'PDF del diario' }}</h1>
    <button
      type="button"
      class="btn btn-solid theme-primary"
      :disabled="!file || salvataggio"
      @click="salva"
    >
      <IconaBs nome="download" class="me-2" />Scarica
    </button>
  </div>

  <StatoCaricamento :in-corso="caricamento" :errore="errore" @riprova="aggiorna">
    <template v-if="file">
      <iframe
        v-if="anteprima && urlAnteprima"
        :src="urlAnteprima"
        class="w-100 rounded-5 border plancia-diari-pdf"
        :title="`Anteprima di ${file.name}`"
      />
      <div v-else class="text-center py-12">
        <IconaBs nome="file-earmark-pdf" class="fs-4xl fg-2 mb-5" />
        <p class="fg-2">File pronto. Premi <strong>Scarica</strong> per aprirlo o salvarlo.</p>
      </div>
    </template>

    <div v-else-if="stato" class="card">
      <div class="card-body text-center py-9" role="status" aria-live="polite">
        <template v-if="stato.stato === 'in_generazione'">
          <span class="spinner-border mb-5" aria-hidden="true" />
          <p class="mb-2">{{ stato.messaggio }}</p>
          <p class="small fg-2 mb-0">La pagina si aggiorna da sola quando il PDF è pronto.</p>
        </template>
        <template v-else-if="stato.stato === 'bloccato'">
          <IconaBs nome="hourglass-split" class="fs-3xl fg-warning mb-5" />
          <p class="mb-0">{{ stato.messaggio }}</p>
        </template>
        <template v-else-if="stato.stato === 'da_generare'">
          <IconaBs nome="file-earmark-pdf" class="fs-3xl fg-2 mb-5" />
          <p>{{ stato.messaggio }}</p>
          <button
            type="button"
            class="btn btn-solid theme-primary"
            :disabled="avvio"
            @click="genera"
          >
            <span v-if="avvio" class="spinner-border spinner-sm me-2" aria-hidden="true" />Genera il
            PDF
          </button>
          <p class="small fg-2 mt-3 mb-0">Riceverai una mail quando il PDF sarà pronto.</p>
        </template>
        <template v-else>
          <span class="spinner-border mb-5" aria-hidden="true" />
          <p class="mb-0">{{ stato.messaggio }}</p>
        </template>
      </div>
    </div>
  </StatoCaricamento>
</template>

<style scoped>
.plancia-diari-pdf {
  height: calc(100svh - 16rem);
  min-height: 400px;
}
</style>
