<script setup lang="ts">
/** Scheda "Sistema": allegati, manutenzione (con messaggio), diagnostica, strumenti collegati. */
import { reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import ImpostazioniInterruttore from '@/components/impostazioni/ImpostazioniInterruttore.vue'
import type { Impostazioni } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useSitoStore } from '@/stores/sito'

const props = defineProps<{ dati: Impostazioni }>()
const emit = defineEmits<{ aggiornate: [Impostazioni] }>()
const sito = useSitoStore()

// --- Allegati -------------------------------------------------------------------------------
const maxPx = ref(String(props.dati.allegati.allegati_max_px))
const allegati = useSalvataggio()
async function salvaAllegati(): Promise<void> {
  const r = await allegati.esegui(
    () => api.patch<Impostazioni>('/impostazioni/allegati', { allegati_max_px: maxPx.value === '' ? null : Number(maxPx.value) }),
    'Allegati salvati.',
  )
  if (r) emit('aggiornate', r)
}

// --- Manutenzione e diagnostica -----------------------------------------------------------------
const d = props.dati.diagnostica
const diagnostica = reactive({
  manutenzione: d.manutenzione,
  manutenzione_messaggio: d.manutenzione_messaggio ?? '',
  debug_toolbar: d.debug_toolbar,
  debug_diagnostico: d.debug_diagnostico,
})
const salvataggio = useSalvataggio()
async function salvaDiagnostica(): Promise<void> {
  if (
    diagnostica.manutenzione &&
    !props.dati.diagnostica.manutenzione &&
    !(await conferma('Attivare la manutenzione? Tutti gli utenti non Admin vedranno la pagina di cortesia e non potranno usare Plancia.', { testoConferma: 'Attiva manutenzione', pericolosa: true }))
  ) {
    return
  }
  const r = await salvataggio.esegui(() => api.patch<Impostazioni>('/impostazioni/diagnostica', diagnostica), 'Stato e diagnostica salvati.')
  if (r) {
    emit('aggiornate', r)
    void sito.carica()
  }
}
</script>

<template>
  <form class="card mb-6" novalidate aria-labelledby="titolo-allegati" @submit.prevent="salvaAllegati">
    <div class="card-body">
      <h2 id="titolo-allegati" class="h5 mb-4"><IconaBs nome="image" class="me-2" />Allegati</h2>
      <div class="row">
        <div class="md:col-4">
          <CampoForm v-model="maxPx" etichetta="Lato maggiore delle immagini (px)" tipo="number" inputmode="numeric" :errori="allegati.errori.value.allegati_max_px" />
        </div>
        <div class="md:col-8">
          <p class="small fg-2 md:pt-6">
            Le immagini caricate come allegati vengono ridimensionate a questo numero di pixel sul lato
            maggiore (JPEG, qualità 85). Il PDF include le immagini a 480&nbsp;px per ridurre la dimensione del file.
          </p>
        </div>
      </div>
      <div class="d-flex justify-content-end">
        <button type="submit" class="btn btn-solid theme-primary" :disabled="allegati.inCorso.value">
          <IconaBs nome="check-lg" class="me-1" />Salva allegati
        </button>
      </div>
    </div>
  </form>

  <form class="card mb-6" novalidate aria-labelledby="titolo-diagnostica" @submit.prevent="salvaDiagnostica">
    <div class="card-body">
      <h2 id="titolo-diagnostica" class="h5 mb-4"><IconaBs nome="sliders" class="me-2" />Stato e diagnostica</h2>
      <div v-if="dati.diagnostica.manutenzione" class="alert theme-danger" role="status">
        <IconaBs nome="cone-striped" class="me-2" />La manutenzione è <strong>attiva</strong>: solo gli Admin possono usare Plancia.
      </div>
      <ImpostazioniInterruttore
        v-model="diagnostica.manutenzione"
        etichetta="Modalità manutenzione"
        descrizione="Mostra una pagina di cortesia a tutti gli utenti non Admin."
      />
      <div class="mb-5">
        <label for="messaggio-manutenzione" class="form-label">Messaggio di manutenzione</label>
        <textarea
          id="messaggio-manutenzione"
          v-model="diagnostica.manutenzione_messaggio"
          class="form-control"
          :class="{ 'is-invalid': salvataggio.errori.value.manutenzione_messaggio }"
          rows="2"
          placeholder="Servizio in manutenzione. Riprovare più tardi."
          aria-describedby="messaggio-manutenzione-aiuto"
        />
        <div id="messaggio-manutenzione-aiuto" class="form-text">Mostrato agli utenti durante la manutenzione. Vuoto = messaggio predefinito.</div>
      </div>
      <div class="row">
        <div class="md:col-6">
          <ImpostazioniInterruttore
            v-model="diagnostica.debug_toolbar"
            etichetta="Debug toolbar"
            descrizione="Mostra la debug toolbar di Django ai soli Admin (non attiva DEBUG)."
          />
        </div>
        <div class="md:col-6">
          <ImpostazioniInterruttore
            v-model="diagnostica.debug_diagnostico"
            etichetta="Log diagnostico"
            descrizione="Alza il livello dei log a DEBUG per facilitare la diagnosi."
          />
        </div>
      </div>
      <div class="d-flex justify-content-end">
        <button type="submit" class="btn btn-solid theme-primary" :disabled="salvataggio.inCorso.value">
          <IconaBs nome="check-lg" class="me-1" />Salva stato e diagnostica
        </button>
      </div>
      <div class="border-top pt-5 mt-5 d-flex flex-wrap gap-3">
        <a href="/celery/" target="_blank" rel="noopener" class="btn btn-outline btn-sm theme-secondary">
          <IconaBs nome="diagram-3" class="me-1" />Flower — dashboard Celery
        </a>
        <a href="/mailadmin/" target="_blank" rel="noopener" class="btn btn-outline btn-sm theme-secondary">
          <IconaBs nome="envelope-open" class="me-1" />Mailpit — email di debug
        </a>
      </div>
    </div>
  </form>

  <section class="card mb-6" aria-labelledby="titolo-strumenti">
    <div class="card-body pb-2">
      <h2 id="titolo-strumenti" class="h5 mb-0"><IconaBs nome="tools" class="me-2" />Strumenti</h2>
    </div>
    <div class="list-group list-group-flush">
      <RouterLink to="/impostazioni/cache-pdf" class="list-group-item list-group-item-action py-4">
        <strong><IconaBs nome="file-earmark-pdf" class="me-2" />Cache e generazione PDF</strong>
        <div class="small fg-2">PDF in cache, invalidazione, generazione massiva per edizione.</div>
      </RouterLink>
      <RouterLink to="/impostazioni/log-export" class="list-group-item list-group-item-action py-4">
        <strong><IconaBs nome="journal-text" class="me-2" />Log generazione PDF / Excel</strong>
        <div class="small fg-2">Storico dei task, errori con traceback, generazioni massive.</div>
      </RouterLink>
      <RouterLink to="/impostazioni/drive" class="list-group-item list-group-item-action py-4">
        <strong><IconaBs nome="cloud-check" class="me-2" />Google Drive</strong>
        <div class="small fg-2">Stato del collegamento e account Drive autorizzati.</div>
      </RouterLink>
      <RouterLink to="/impostazioni/aggiornamenti" class="list-group-item list-group-item-action py-4">
        <strong><IconaBs nome="cloud-arrow-down" class="me-2" />Aggiornamenti del server</strong>
        <div class="small fg-2">Versione installata, nuove release, aggiornamento dal web.</div>
      </RouterLink>
      <RouterLink to="/import" class="list-group-item list-group-item-action py-4">
        <strong><IconaBs nome="upload" class="me-2" />Import tracciati</strong>
        <div class="small fg-2">Carica i tracciati CSV (Co.Ca., Squadriglie iscritte, Ragazzi) e consulta lo storico.</div>
      </RouterLink>
    </div>
  </section>
</template>
