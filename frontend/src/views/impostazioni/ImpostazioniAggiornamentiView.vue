<script setup lang="ts">
/**
 * Aggiornamenti del server dal web (solo Admin): versione installata, ultima release con le
 * note, "Controlla ora", "Aggiorna a vX.Y.Z" (conferma + riautenticazione), monitoraggio
 * dell'avanzamento che regge il riavvio del server, annullamento e storico.
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { api, ErroreApi, type Pagina } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import type { Aggiornamenti } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import {
  righeLog,
  useMonitoraggioAggiornamento,
  type Fase,
  type RichiestaAggiornamento,
} from '@/composables/impostazioni-aggiornamento'
import { dataOra } from '@/composables/impostazioni-editor'
import { markdownSicuro } from '@/composables/impostazioni-markdown'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { conRiautenticazione } from '@/composables/riautenticazione'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const avvisi = useAvvisiStore()
const riepilogo = useRichiesta(() => api.get<Aggiornamenti>('/aggiornamenti'))
const r = computed(() => riepilogo.dati.value)
const note = computed(() => markdownSicuro(r.value?.ultima?.note ?? ''))

// --- Storico ----------------------------------------------------------------------------------
const LIMITE = 10
const offset = ref(0)
const storico = useRichiesta(() =>
  api.get<Pagina<RichiestaAggiornamento>>('/aggiornamenti/storico', { limit: LIMITE, offset: offset.value }),
)
watch(offset, storico.esegui)

// --- Monitoraggio -----------------------------------------------------------------------------
const ricaricoTra = ref(0)
const monitor = useMonitoraggioAggiornamento({
  allaFine: (fase: Fase) => {
    if (fase === 'completato') {
      avvisi.mostra('Aggiornamento completato: ricarico Plancia con la nuova versione.', 'success', 0)
      ricaricoTra.value = 5
      const conto = setInterval(() => {
        ricaricoTra.value--
        if (ricaricoTra.value <= 0) {
          clearInterval(conto)
          window.location.reload()
        }
      }, 1000)
    } else {
      void riepilogo.esegui()
      void storico.esegui()
    }
  },
})
const richiesta = computed(() => monitor.stato.value?.richiesta ?? r.value?.richiesta_in_corso ?? null)
const statoGrezzo = computed(() => (monitor.stato.value?.stato ?? null) as Record<string, unknown> | null)
const messaggio = computed(() => String(statoGrezzo.value?.messaggio ?? richiesta.value?.messaggio ?? ''))
const percentuale = computed(() => {
  const p = statoGrezzo.value?.percentuale ?? richiesta.value?.percentuale
  return typeof p === 'number' ? Math.max(0, Math.min(100, p)) : null
})
const log = computed(() => righeLog(monitor.stato.value))
const monitorAttivo = computed(() => monitor.fase.value !== 'inattivo')
/**
 * Annullabile finché il runner non l'ha presa: la richiesta resta `in_attesa` finché
 * `in-corso.json` non esiste (poi lo storico la porta `in_corso`); il backend lo ricontrolla (409).
 */
const annullabile = computed(() => richiesta.value?.stato === 'in_attesa' && monitor.fase.value === 'in_corso')
const ETICHETTE_FASE: Record<Fase, string> = {
  in_corso: 'In corso',
  riavvio: 'Server in riavvio…',
  completato: 'Completato',
  fallito: 'Fallito',
  annullato: 'Annullato',
  errore: 'Errore',
  inattivo: '',
}

const COLORI_STATO: Record<string, string> = { completato: 'success', fallito: 'danger', annullato: 'secondary' }

const riquadroLog = ref<HTMLElement>()
watch(log, async () => {
  await nextTick()
  const el = riquadroLog.value
  if (el) el.scrollTop = el.scrollHeight
})

onMounted(async () => {
  const dati = await riepilogo.esegui()
  void storico.esegui()
  if (dati?.richiesta_in_corso) monitor.avvia(dati.installata)
})

// --- Azioni -----------------------------------------------------------------------------------
const azione = useSalvataggio()

async function controlla(): Promise<void> {
  const nuovo = await azione.esegui(() => api.post<Aggiornamenti>('/aggiornamenti/controlla'))
  if (!nuovo) return
  riepilogo.dati.value = nuovo
  if (nuovo.ultima?.errore) avvisi.mostra(`Controllo non riuscito: ${nuovo.ultima.errore}`, 'warning', 10000)
  else if (nuovo.aggiornamento_disponibile) avvisi.mostra(`È disponibile la versione ${nuovo.ultima?.versione}.`, 'info')
  else avvisi.mostra('Plancia è aggiornata.')
}

async function aggiorna(): Promise<void> {
  const versione = r.value?.ultima?.versione
  if (!versione || !r.value) return
  const ok = await conferma(
    `Aggiornare il server da v${r.value.installata} a ${versione}? Plancia andrà in manutenzione per qualche minuto (backup, costruzione e riavvio); se qualcosa va storto si torna alla versione precedente.`,
    { titolo: `Aggiorna a ${versione}`, testoConferma: `Aggiorna a ${versione}`, pericolosa: true },
  )
  if (!ok) return
  const installata = r.value.installata
  const creata = await azione.esegui(
    () => conRiautenticazione(() => api.post<RichiestaAggiornamento>('/aggiornamenti/richiesta', { versione })),
    `Aggiornamento a ${versione} richiesto: il server lo avvierà a breve.`,
  )
  if (!creata) {
    // es. 409: c'è già una richiesta aperta (da un'altra scheda): la si segue
    const dati = await riepilogo.esegui()
    if (dati?.richiesta_in_corso) monitor.avvia(installata)
    return
  }
  if (riepilogo.dati.value) riepilogo.dati.value = { ...riepilogo.dati.value, richiesta_in_corso: creata }
  monitor.avvia(installata)
  void storico.esegui()
}

async function annulla(): Promise<void> {
  if (!(await conferma("Annullare la richiesta di aggiornamento? È possibile solo finché il server non l'ha presa in carico.", { testoConferma: 'Annulla la richiesta', pericolosa: true }))) {
    return
  }
  try {
    await api.post<RichiestaAggiornamento>('/aggiornamenti/richiesta/annulla')
    avvisi.mostra('Richiesta di aggiornamento annullata.')
    monitor.ferma()
    monitor.fase.value = 'inattivo'
    monitor.stato.value = null
    await Promise.all([riepilogo.esegui(), storico.esegui()])
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Annullamento non riuscito.', 'danger', 8000)
  }
}
</script>

<template>
  <h1 class="h3 mb-5">Aggiornamenti del server</h1>

  <StatoCaricamento :in-corso="riepilogo.inCorso.value && !r" :errore="riepilogo.errore.value" @riprova="riepilogo.esegui">
    <template v-if="r">
      <section class="card mb-6" aria-labelledby="titolo-versioni">
        <div class="card-body">
          <h2 id="titolo-versioni" class="visually-hidden">Versioni</h2>
          <div class="row">
            <div class="md:col-4 mb-4">
              <div class="small fg-2">Versione installata</div>
              <div class="h4 mb-0">v{{ r.installata }}</div>
            </div>
            <div class="md:col-4 mb-4">
              <div class="small fg-2">Ultima release</div>
              <div class="h4 mb-0">
                {{ r.ultima?.versione || '—' }}
                <span v-if="r.aggiornamento_disponibile" class="badge theme-info align-middle ms-2">disponibile</span>
                <span v-else-if="r.ultima?.versione" class="badge theme-success align-middle ms-2">aggiornato</span>
              </div>
              <div v-if="r.ultima?.pubblicata_at" class="small fg-2">pubblicata il {{ dataOra(r.ultima.pubblicata_at) }}</div>
            </div>
            <div class="md:col-4 mb-4">
              <div class="small fg-2">Ultimo controllo</div>
              <div>{{ dataOra(r.ultima?.controllata_at) }}</div>
            </div>
          </div>
          <div v-if="r.ultima?.errore" class="alert theme-warning small" role="alert">
            <IconaBs nome="exclamation-triangle" class="me-2" />Ultimo controllo non riuscito: {{ r.ultima.errore }}
          </div>
          <div class="d-flex flex-wrap gap-3">
            <button type="button" class="btn btn-outline theme-secondary" :disabled="azione.inCorso.value" @click="controlla">
              <IconaBs nome="arrow-repeat" class="me-1" />Controlla ora
            </button>
            <button
              v-if="r.aggiornamento_disponibile && r.ultima"
              type="button"
              class="btn btn-solid theme-primary"
              :disabled="azione.inCorso.value || !!r.richiesta_in_corso || monitorAttivo"
              @click="aggiorna"
            >
              <IconaBs nome="cloud-arrow-down" class="me-1" />Aggiorna a {{ r.ultima.versione }}
            </button>
          </div>
        </div>
      </section>

      <section v-if="monitorAttivo || r.richiesta_in_corso" class="card mb-6" aria-labelledby="titolo-avanzamento">
        <div class="card-body">
          <div class="d-flex flex-wrap align-items-center gap-3 mb-3">
            <h2 id="titolo-avanzamento" class="h5 mb-0">
              Aggiornamento {{ richiesta?.versione_partenza ? `da v${richiesta.versione_partenza} ` : '' }}a {{ richiesta?.versione }}
            </h2>
            <span
              class="badge"
              :class="{
                'theme-warning': monitor.fase.value === 'in_corso' || monitor.fase.value === 'riavvio',
                'theme-success': monitor.fase.value === 'completato',
                'theme-danger': monitor.fase.value === 'fallito' || monitor.fase.value === 'errore',
                'theme-secondary': monitor.fase.value === 'annullato',
              }"
            >
              <span v-if="monitor.fase.value === 'in_corso' || monitor.fase.value === 'riavvio'" class="spinner-border spinner-border-sm me-1" aria-hidden="true" />
              {{ ETICHETTE_FASE[monitor.fase.value] || richiesta?.stato_display }}
            </span>
            <button v-if="annullabile" type="button" class="btn btn-outline btn-sm theme-danger ms-auto" @click="annulla">
              <IconaBs nome="x-circle" class="me-1" />Annulla la richiesta
            </button>
          </div>

          <p class="mb-2" aria-live="polite">
            <template v-if="monitor.fase.value === 'riavvio'">
              Il server si sta riavviando: Plancia non risponde per qualche istante, riprovo in automatico…
            </template>
            <template v-else-if="monitor.fase.value === 'completato'">
              Aggiornamento completato.<template v-if="ricaricoTra > 0"> Ricarico l'app tra {{ ricaricoTra }} s…</template>
            </template>
            <template v-else-if="monitor.fase.value === 'errore'">{{ monitor.errore.value }}</template>
            <template v-else>{{ messaggio || (richiesta?.stato === 'in_attesa' ? 'In attesa che il server prenda in carico la richiesta…' : '') }}</template>
          </p>
          <div v-if="statoGrezzo?.fase" class="small fg-2 mb-3">Fase: {{ statoGrezzo.fase }}</div>

          <div
            v-if="percentuale !== null"
            class="progress mb-4"
            role="progressbar"
            aria-label="Avanzamento dell'aggiornamento"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-valuenow="percentuale"
          >
            <div class="progress-bar" :class="monitor.fase.value === 'fallito' ? 'theme-danger' : 'theme-success'" :style="{ width: `${percentuale}%` }">
              {{ percentuale }}%
            </div>
          </div>

          <div v-if="log.length" ref="riquadroLog" class="impostazioni-log-aggiornamento small rounded p-3" tabindex="0" aria-label="Log dell'aggiornamento">
            <div v-for="(riga, i) in log" :key="i">{{ riga }}</div>
          </div>
          <p v-if="monitor.fase.value === 'fallito'" class="small mt-3 mb-0">
            Il log completo è sul server in <code>aggiornamenti/log/</code>; l'Admin riceve anche un'email con l'esito.
          </p>
        </div>
      </section>

      <section v-if="r.ultima" class="card mb-6" aria-labelledby="titolo-note">
        <div class="card-body">
          <div class="d-flex flex-wrap align-items-center gap-3 mb-3">
            <h2 id="titolo-note" class="h5 mb-0">Novità di {{ r.ultima.versione }}<template v-if="r.ultima.nome && r.ultima.nome !== r.ultima.versione"> — {{ r.ultima.nome }}</template></h2>
            <a v-if="r.ultima.url" :href="r.ultima.url" target="_blank" rel="noopener noreferrer" class="btn btn-text btn-sm theme-secondary ms-auto">
              <IconaBs nome="box-arrow-up-right" class="me-1" />Apri su GitHub
            </a>
          </div>
          <!-- markdownSicuro: testo sempre "escapato", solo tag generati dal convertitore -->
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-if="note" class="impostazioni-note" v-html="note" />
          <p v-else class="fg-2 mb-0">Nessuna nota di rilascio.</p>
        </div>
      </section>
    </template>
  </StatoCaricamento>

  <section class="card mb-6" aria-labelledby="titolo-storico">
    <div class="card-body">
      <h2 id="titolo-storico" class="h5 mb-4">Storico degli aggiornamenti</h2>
      <StatoCaricamento
        :in-corso="storico.inCorso.value && !storico.dati.value"
        :errore="storico.errore.value"
        :vuoto="!storico.dati.value?.items.length"
        messaggio-vuoto="Nessun aggiornamento richiesto dal web."
        @riprova="storico.esegui"
      >
        <ul class="list-group">
          <li v-for="s in storico.dati.value?.items" :key="s.id" class="list-group-item py-3">
            <div class="d-flex flex-wrap align-items-center gap-3">
              <strong>{{ s.versione_partenza ? `v${s.versione_partenza} → ` : '' }}{{ s.versione }}</strong>
              <span class="badge" :class="`theme-${COLORI_STATO[s.stato] ?? 'warning'}`">{{ s.stato_display }}</span>
              <span class="small fg-2 ms-auto">{{ dataOra(s.richiesta_at) }} · {{ s.richiesta_da }}</span>
            </div>
            <div v-if="s.messaggio" class="small mt-1">{{ s.messaggio }}</div>
            <div v-if="s.completato_at" class="small fg-2">Concluso il {{ dataOra(s.completato_at) }}</div>
            <details v-if="s.log" class="mt-2">
              <summary class="small">Log</summary>
              <pre class="impostazioni-log-aggiornamento small rounded p-3 mt-2 mb-0">{{ s.log }}</pre>
            </details>
          </li>
        </ul>
        <PaginazioneElenco v-model:offset="offset" :totale="storico.dati.value?.count ?? 0" :limite="LIMITE" />
      </StatoCaricamento>
    </div>
  </section>
</template>

<style scoped>
.impostazioni-log-aggiornamento {
  font-family: var(--bs-font-monospace, ui-monospace, SFMono-Regular, Menlo, monospace);
  white-space: pre-wrap;
  word-break: break-word;
  background: #1e1e1e;
  color: #e6e6e6;
  max-height: 18rem;
  overflow-y: auto;
}
.impostazioni-note :deep(h3),
.impostazioni-note :deep(h4) {
  font-size: 1.05rem;
  margin-top: 1rem;
}
</style>
