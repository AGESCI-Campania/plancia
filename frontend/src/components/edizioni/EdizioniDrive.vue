<script setup lang="ts">
/**
 * Google Drive dell'edizione: collegamento dell'account (OAuth, ritorno su questa pagina),
 * scelta delle cartelle Allegati e Output e del formato del nome cartella dei diari.
 * Quando tutti e tre sono valorizzati la configurazione si blocca per sempre
 * (`cartelle_configurate`): prima di salvare si chiede conferma.
 */
import { computed, onMounted, ref, useId } from 'vue'

import { api, ErroreApi } from '@/api/http'
import type { Cartella, CartellaInfo, DriveEdizione, StatoDrive } from '@/api/tipi-edizioni'
import EdizioniSelettoreCartella from '@/components/edizioni/EdizioniSelettoreCartella.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { conferma } from '@/composables/conferma'
import { anteprimaCartella, VARIABILI_CARTELLA } from '@/composables/edizioni'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ edizioneId: number; anno: number }>()
const avvisi = useAvvisiStore()
const id = useId()

type Destinazione = 'allegati' | 'output'

const config = useRichiesta(() => api.get<DriveEdizione>(`/drive/edizioni/${props.edizioneId}`))
const stato = useRichiesta(() => api.get<StatoDrive>('/drive/stato'))

const allegati = ref('')
const output = ref('')
const formato = ref('')
const info = ref<Record<Destinazione, CartellaInfo | null>>({ allegati: null, output: null })
const errori = ref<Record<string, string[]>>({})
const errore = ref('')
const salvataggio = ref(false)
const collegamento = ref(false)
const picker = ref(false)
const destinazione = ref<Destinazione>('allegati')

const c = computed(() => config.dati.value)
const bloccata = computed(() => c.value?.cartelle_configurate ?? false)
const anteprima = computed(() => anteprimaCartella(formato.value || c.value?.cartella_diario_format || '', props.anno))
const completa = computed(() => Boolean(allegati.value.trim() && output.value.trim() && (formato.value.trim() || c.value?.cartella_diario_format)))

async function caricaInfo(dest: Destinazione, folderId: string): Promise<void> {
  info.value[dest] = null
  if (!folderId || !c.value?.account_collegato) return
  try {
    info.value[dest] = await api.get<CartellaInfo>(`/drive/cartelle/${encodeURIComponent(folderId)}`, {
      account: c.value.account,
    })
  } catch {
    // cartella non leggibile: resta l'id
  }
}

async function carica(): Promise<void> {
  await Promise.all([config.esegui(), stato.esegui()])
  const d = c.value
  if (!d) return
  allegati.value = d.drive_folder_allegati_id
  output.value = d.drive_folder_output_id
  formato.value = d.cartella_diario_format
  void caricaInfo('allegati', d.drive_folder_allegati_id)
  void caricaInfo('output', d.drive_folder_output_id)
}
onMounted(carica)

async function collega(): Promise<void> {
  collegamento.value = true
  try {
    const { url } = await api.post<{ url: string }>('/drive/oauth', { edizione_id: props.edizioneId })
    window.location.assign(url)
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Collegamento non avviato.', 'danger')
    collegamento.value = false
  }
}

function imposta(dest: Destinazione, valore: string): void {
  if (dest === 'allegati') allegati.value = valore
  else output.value = valore
  info.value[dest] = null
}

function sfoglia(dest: Destinazione): void {
  destinazione.value = dest
  picker.value = true
}

function scelta(cartella: Cartella): void {
  if (destinazione.value === 'allegati') allegati.value = cartella.id
  else output.value = cartella.id
  info.value[destinazione.value] = {
    id: cartella.id,
    nome: cartella.nome,
    url: `https://drive.google.com/drive/folders/${cartella.id}`,
  }
}

async function salva(): Promise<void> {
  errore.value = ''
  errori.value = {}
  if (completa.value) {
    const ok = await conferma(
      'Con cartella Allegati, cartella Output e formato del nome tutti valorizzati la configurazione ' +
        'viene bloccata: non potrai più cambiarli per questa edizione. Controlla i valori prima di continuare.',
      { titolo: 'Salvare e bloccare la configurazione?', testoConferma: 'Salva e blocca', pericolosa: true },
    )
    if (!ok) return
  }
  salvataggio.value = true
  try {
    config.dati.value = await api.put<DriveEdizione>(`/drive/edizioni/${props.edizioneId}`, {
      drive_folder_allegati_id: allegati.value.trim(),
      drive_folder_output_id: output.value.trim(),
      cartella_diario_format: formato.value.trim(),
    })
    avvisi.mostra(bloccata.value ? 'Configurazione Drive salvata e bloccata.' : 'Configurazione Drive salvata.')
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = e.errori
      errore.value = e.message
    } else {
      errore.value = 'Salvataggio non riuscito.'
    }
  } finally {
    salvataggio.value = false
  }
}
</script>

<template>
  <section class="card mb-6" aria-labelledby="titolo-drive">
    <div class="card-header flex-row flex-wrap align-items-center gap-3">
      <IconaBs nome="google" />
      <h2 id="titolo-drive" class="h5 mb-0">Google Drive</h2>
      <span v-if="c?.account" class="badge ms-auto" :class="c.account_collegato ? 'theme-success' : 'theme-warning'">
        {{ c.account }}
      </span>
      <span v-else-if="c" class="badge theme-secondary ms-auto">Non collegato</span>
    </div>
    <div class="card-body">
      <StatoCaricamento :in-corso="config.inCorso.value" :errore="config.errore.value" @riprova="carica">
        <template v-if="c">
          <div v-if="!bloccata" class="mb-5">
            <button
              type="button"
              class="btn btn-outline btn-sm theme-primary"
              :disabled="collegamento || stato.dati.value?.oauth_configurato === false"
              @click="collega"
            >
              <span v-if="collegamento" class="spinner-border spinner-sm me-2" aria-hidden="true" />
              {{ c.account ? 'Cambia account Drive' : 'Connetti account Google Drive' }}
            </button>
            <p v-if="stato.dati.value?.oauth_configurato === false" class="small fg-warning mt-2 mb-0">
              Il client OAuth di Google non è configurato sul server: chiedi all'amministratore.
            </p>
            <p v-else-if="!c.account" class="small fg-2 mt-2 mb-0">Connetti un account per scegliere le cartelle.</p>
            <p v-else-if="!c.account_collegato" class="small fg-warning mt-2 mb-0">
              L'account {{ c.account }} non è più collegato a Plancia: ricollegalo per scegliere le cartelle.
            </p>
          </div>

          <template v-if="bloccata">
            <div class="alert theme-warning d-flex align-items-center gap-3" role="status">
              <IconaBs nome="lock-fill" />
              <span><strong>Configurazione bloccata.</strong> Le cartelle principali e il formato non
                possono essere modificati dopo la prima configurazione.</span>
            </div>
            <dl class="row mb-0">
              <dt class="col-12 sm:col-4">Cartella Allegati</dt>
              <dd class="col-12 sm:col-8">
                <a v-if="info.allegati?.url" :href="info.allegati.url" target="_blank" rel="noopener">
                  <IconaBs nome="folder2" class="me-1" />{{ info.allegati.nome }}</a>
                <code v-else>{{ c.drive_folder_allegati_id }}</code>
              </dd>
              <dt class="col-12 sm:col-4">Cartella Output</dt>
              <dd class="col-12 sm:col-8">
                <a v-if="info.output?.url" :href="info.output.url" target="_blank" rel="noopener">
                  <IconaBs nome="folder2" class="me-1" />{{ info.output.nome }}</a>
                <code v-else>{{ c.drive_folder_output_id }}</code>
              </dd>
              <dt class="col-12 sm:col-4">Formato nome cartella diario</dt>
              <dd class="col-12 sm:col-8">
                <code>{{ c.cartella_diario_format }}</code>
                <div class="small fg-2">Esempio: <code>{{ anteprima }}</code></div>
              </dd>
            </dl>
          </template>

          <form v-else-if="c.account_collegato" novalidate @submit.prevent="salva">
            <div class="alert theme-info small" role="note">
              <IconaBs nome="info-circle" class="me-1" />
              Una volta salvate tutte e tre, le cartelle e il formato <strong>non potranno più essere
                modificati</strong>. Verifica i valori prima di salvare.
            </div>
            <div v-if="errore" class="alert theme-danger" role="alert">{{ errore }}</div>

            <div v-for="dest in (['allegati', 'output'] as const)" :key="dest" class="mb-5">
              <label :for="`${id}-${dest}`" class="form-label">
                Cartella {{ dest === 'allegati' ? 'Allegati' : 'Output' }} <span class="fg-danger" aria-hidden="true">*</span>
              </label>
              <div class="input-group">
                <input
                  :id="`${id}-${dest}`"
                  :value="dest === 'allegati' ? allegati : output"
                  type="text"
                  class="form-control font-monospace"
                  :class="{ 'is-invalid': errori[`drive_folder_${dest}_id`]?.length }"
                  placeholder="ID cartella Drive"
                  required
                  :aria-describedby="`${id}-${dest}-info`"
                  @input="imposta(dest, ($event.target as HTMLInputElement).value)"
                  @change="caricaInfo(dest, dest === 'allegati' ? allegati : output)"
                />
                <button type="button" class="btn btn-outline theme-secondary" @click="sfoglia(dest)">Sfoglia</button>
              </div>
              <div :id="`${id}-${dest}-info`" class="form-text">
                <a v-if="info[dest]?.url" :href="info[dest]!.url" target="_blank" rel="noopener">
                  <IconaBs nome="folder2" class="me-1" />{{ info[dest]!.nome }}</a>
              </div>
              <div v-for="e in errori[`drive_folder_${dest}_id`] ?? []" :key="e" class="invalid-feedback d-block">{{ e }}</div>
            </div>

            <div class="mb-5">
              <label :for="`${id}-formato`" class="form-label">
                Formato nome cartella diario <span class="fg-danger" aria-hidden="true">*</span>
              </label>
              <input
                :id="`${id}-formato`"
                v-model="formato"
                type="text"
                class="form-control font-monospace"
                :class="{ 'is-invalid': errori.cartella_diario_format?.length }"
                :aria-describedby="`${id}-formato-aiuto`"
              />
              <div v-for="e in errori.cartella_diario_format ?? []" :key="e" class="invalid-feedback d-block">{{ e }}</div>
              <div :id="`${id}-formato-aiuto`" class="form-text">
                Variabili disponibili:
                <template v-for="(_, v) in VARIABILI_CARTELLA" :key="v"><code>{{ v }}</code>{{ ' ' }}</template>
                (<code>{id_univoco}</code> obbligatoria).
                <br />Anteprima: <code>{{ anteprima }}</code>
              </div>
            </div>

            <button type="submit" class="btn btn-solid btn-sm theme-primary" :disabled="salvataggio">
              <span v-if="salvataggio" class="spinner-border spinner-sm me-2" aria-hidden="true" />
              <IconaBs v-else :nome="completa ? 'lock' : 'save'" class="me-1" />
              {{ completa ? 'Salva e blocca configurazione' : 'Salva' }}
            </button>
          </form>

          <EdizioniSelettoreCartella
            v-if="c.account_collegato && !bloccata"
            v-model:aperta="picker"
            :account="c.account"
            :titolo="`Scegli la cartella ${destinazione === 'allegati' ? 'Allegati' : 'Output'}`"
            @scelta="scelta"
          />
        </template>
      </StatoCaricamento>
    </div>
  </section>
</template>
