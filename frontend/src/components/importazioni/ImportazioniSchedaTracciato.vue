<script setup lang="ts">
/**
 * Scheda di lancio di un tracciato: file (con controllo dell'estensione), edizione dove
 * serve, avvio. L'import gira in background: il 202 porta il messaggio da mostrare.
 */
import { computed, ref, useId, useTemplateRef } from 'vue'

import { ErroreApi, richiesta, type ErroriCampo } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import {
  chiedeEdizione,
  descrizione,
  etichettaEdizione,
  validaLancio,
  type EdizioneBreve,
  type EsitoLancio,
  type Tracciato,
} from '@/components/importazioni/importazioni'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ tracciato: Tracciato; numero: number; edizioni: EdizioneBreve[] }>()
const emit = defineEmits<{ avviato: [esito: EsitoLancio] }>()

const avvisi = useAvvisiStore()
const id = useId()
const info = computed(() => descrizione(props.tracciato.chiave))
const conEdizione = computed(() => chiedeEdizione(props.tracciato))

const inputFile = useTemplateRef<HTMLInputElement>('inputFile')
const file = ref<File | null>(null)
const edizionePk = ref('')
const errori = ref<ErroriCampo>({})
const erroreGenerale = ref('')
const inCorso = ref(false)

function sceltoFile(evento: Event): void {
  file.value = (evento.target as HTMLInputElement).files?.[0] ?? null
  // Controllo immediato dell'estensione, prima ancora di premere "Importa"
  const e = validaLancio(props.tracciato, file.value, edizionePk.value)
  errori.value = file.value && e.file ? { file: e.file } : {}
}

async function avvia(): Promise<void> {
  erroreGenerale.value = ''
  errori.value = validaLancio(props.tracciato, file.value, edizionePk.value)
  if (Object.keys(errori.value).length) return
  const dati = new FormData()
  dati.append('file', file.value as File)
  if (edizionePk.value) dati.append('edizione_pk', edizionePk.value)
  inCorso.value = true
  try {
    const esito = await richiesta<EsitoLancio>(
      `/api/v1/importazioni/lancia/${encodeURIComponent(props.tracciato.chiave)}`,
      { metodo: 'POST', corpo: dati },
    )
    avvisi.mostra(esito.messaggio, 'success', 8000)
    file.value = null
    edizionePk.value = ''
    if (inputFile.value) inputFile.value.value = ''
    emit('avviato', esito)
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = e.errori
      const campi = ['file', 'edizione_pk']
      const altri = Object.entries(e.errori).filter(([k]) => !campi.includes(k)).flatMap(([, v]) => v)
      erroreGenerale.value = altri.join(' ') || (Object.keys(e.errori).length ? '' : e.message)
    } else erroreGenerale.value = 'Errore imprevisto.'
  } finally {
    inCorso.value = false
  }
}
</script>

<template>
  <section class="card h-100" :aria-labelledby="`${id}-titolo`">
    <div class="card-header flex-row flex-wrap align-items-center gap-2 small fw-semibold">
      <IconaBs :nome="info.icona" />
      <h3 :id="`${id}-titolo`" class="h6 mb-0">{{ numero }}. {{ tracciato.etichetta }}</h3>
      <span v-if="info.nota" class="badge theme-secondary fw-normal">{{ info.nota }}</span>
    </div>
    <form class="card-body d-flex flex-column" novalidate @submit.prevent="avvia">
      <p v-if="info.descrizione" class="small fg-2 mb-4">{{ info.descrizione }}</p>

      <div v-if="conEdizione" class="mb-3">
        <label :for="`${id}-edizione`" class="form-label small">
          Edizione<span v-if="tracciato.edizione_obbligatoria"> (obbligatoria)</span>
        </label>
        <select
          :id="`${id}-edizione`"
          v-model="edizionePk"
          class="form-control form-control-sm"
          :class="{ 'is-invalid': errori.edizione_pk?.length }"
          :required="tracciato.edizione_obbligatoria"
          :aria-describedby="errori.edizione_pk?.length ? `${id}-edizione-err` : undefined"
        >
          <option value="">
            {{ tracciato.edizione_obbligatoria ? '— Seleziona edizione —' : `— ${info.edizioneVuota ?? 'Nessuna'} —` }}
          </option>
          <option v-for="ed in edizioni" :key="ed.id" :value="String(ed.id)">
            {{ etichettaEdizione(ed) }} ({{ ed.stato_display }})
          </option>
        </select>
        <div v-if="errori.edizione_pk?.length" :id="`${id}-edizione-err`" class="invalid-feedback">
          {{ errori.edizione_pk.join(' ') }}
        </div>
      </div>

      <div class="mb-4">
        <label :for="`${id}-file`" class="form-label small">File {{ tracciato.estensione }}</label>
        <input
          :id="`${id}-file`"
          ref="inputFile"
          type="file"
          name="file"
          :accept="tracciato.estensione"
          class="form-control form-control-sm"
          :class="{ 'is-invalid': errori.file?.length }"
          required
          :aria-describedby="errori.file?.length ? `${id}-file-err` : undefined"
          @change="sceltoFile"
        />
        <div v-if="errori.file?.length" :id="`${id}-file-err`" class="invalid-feedback">
          {{ errori.file.join(' ') }}
        </div>
      </div>

      <div v-if="erroreGenerale" class="alert theme-danger small py-2" role="alert">{{ erroreGenerale }}</div>

      <button type="submit" class="btn btn-outline theme-primary btn-sm w-100 mt-auto plancia-btn-a-capo" :disabled="inCorso">
        <span v-if="inCorso" class="spinner-border spinner-sm me-1" aria-hidden="true" />
        <IconaBs v-else nome="upload" class="me-1" />
        Importa {{ tracciato.etichetta }}
      </button>
    </form>
  </section>
</template>

<style scoped>
/* Etichette lunghe ("Importa Squadriglie iscritte") vanno a capo invece di uscire dal bordo */
.plancia-btn-a-capo {
  white-space: normal;
  height: auto;
}
</style>
