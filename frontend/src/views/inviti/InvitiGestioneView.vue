<script setup lang="ts">
/**
 * Gestione inviti (staff), edizione attiva: contatori e invio a tutti i Capi Reparto o a tutti
 * i Capi Squadriglia (canale standard o massivo), elenco per squadriglia con filtri, stato di
 * consegna, invio degli inviti mancanti di un diario e reinvio dei singoli inviti.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api, ErroreApi, type Pagina } from '@/api/http'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import IconaBs from '@/components/IconaBs.vue'
import PaginazioneElenco from '@/components/PaginazioneElenco.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import InvitiBadgeInvito from '@/components/inviti/InvitiBadgeInvito.vue'
import { ordinaRighe, type ColonnaOrdinamento } from '@/components/inviti/ordinamento'
import { messaggioErrore, offsetQuery, testoQuery } from '@/components/utenti/formato'
import type { RiepilogoInviti, RigaInviti } from '@/components/utenti/tipi'
import { conferma } from '@/composables/conferma'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

type TipoInvio = 'capi' | 'csq'
type Canale = 'massivo' | 'standard'

const LIMITE = 50
const route = useRoute()
const router = useRouter()
const avvisi = useAvvisiStore()

const q = ref(testoQuery(route.query.q))
const zona = ref(testoQuery(route.query.zona))
const gruppo = ref(testoQuery(route.query.gruppo))
const offset = ref(offsetQuery(route.query.offset))

const riepilogo = useRichiesta(() => api.get<RiepilogoInviti>('/notifiche/inviti/riepilogo'))
const elenco = useRichiesta(() =>
  api.get<Pagina<RigaInviti>>('/notifiche/inviti', {
    q: q.value.trim(),
    zona: zona.value,
    gruppo: gruppo.value,
    limit: LIMITE,
    offset: offset.value,
  }),
)
const filtriAttivi = computed(() => Boolean(q.value || zona.value || gruppo.value))

// --- Filtri nella query dell'URL -------------------------------------------------------
function aggiornaUrl(): void {
  void router.replace({
    query: {
      ...(q.value.trim() ? { q: q.value.trim() } : {}),
      ...(zona.value ? { zona: zona.value } : {}),
      ...(gruppo.value ? { gruppo: gruppo.value } : {}),
      ...(offset.value ? { offset: String(offset.value) } : {}),
    },
  })
  void elenco.esegui()
}
function daCapo(): void {
  if (offset.value) offset.value = 0
  else aggiornaUrl()
}
let timer: ReturnType<typeof setTimeout> | undefined
watch(q, () => {
  clearTimeout(timer)
  timer = setTimeout(daCapo, 300)
})
watch([zona, gruppo], daCapo)
watch(offset, aggiornaUrl)
function azzera(): void {
  clearTimeout(timer)
  q.value = ''
  zona.value = ''
  gruppo.value = ''
}

// --- Ordinamento (sulla pagina mostrata) ---------------------------------------------------
const colonna = ref<ColonnaOrdinamento | null>(null)
const crescente = ref(true)
const righe = computed(() =>
  colonna.value ? ordinaRighe(elenco.dati.value?.items ?? [], colonna.value, crescente.value) : (elenco.dati.value?.items ?? []),
)
function ordina(c: ColonnaOrdinamento): void {
  if (colonna.value === c) crescente.value = !crescente.value
  else {
    colonna.value = c
    crescente.value = true
  }
}
function ariaSort(c: ColonnaOrdinamento): 'ascending' | 'descending' | 'none' {
  if (colonna.value !== c) return 'none'
  return crescente.value ? 'ascending' : 'descending'
}

// --- Invio per edizione ----------------------------------------------------------------------
const canale = ref<Record<TipoInvio, Canale>>({ capi: 'massivo', csq: 'massivo' })
const inviando = ref<TipoInvio | null>(null)

async function inviaEdizione(tipo: TipoInvio): Promise<void> {
  const destinatari = tipo === 'capi' ? 'Capi Reparto' : 'Capi Squadriglia'
  const n = tipo === 'capi' ? riepilogo.dati.value?.contatori?.capi_da_invitare : riepilogo.dati.value?.contatori?.csq_da_invitare
  const ok = await conferma(`Inviare gli inviti ai ${destinatari} ancora da invitare (${n ?? 0})?`, {
    titolo: `Invia inviti ai ${destinatari}`,
    testoConferma: 'Invia',
  })
  if (!ok) return
  inviando.value = tipo
  try {
    const r = await api.post<{ detail: string }>('/notifiche/inviti/invia-edizione', { tipo, backend: canale.value[tipo] })
    avvisi.mostra(r.detail)
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? messaggioErrore(e.message, e.errori) : 'Invio non riuscito.', 'danger')
  } finally {
    inviando.value = null
  }
}

// --- Invio per diario -------------------------------------------------------------------------
const rigaInvio = ref<RigaInviti | null>(null)
const dialogoDiario = ref(false)
const ruoliDiario = ref<('csq' | 'crp')[]>(['csq', 'crp'])
const erroreDiario = ref('')

function apriInvioDiario(r: RigaInviti): void {
  rigaInvio.value = r
  ruoliDiario.value = [...(r.ultimo_invito_csq ? [] : (['csq'] as const)), ...(r.ultimo_invito_crp ? [] : (['crp'] as const))]
  if (!ruoliDiario.value.length) ruoliDiario.value = ['csq', 'crp']
  erroreDiario.value = ''
  dialogoDiario.value = true
}

async function inviaDiario(): Promise<void> {
  if (!rigaInvio.value) return
  if (!ruoliDiario.value.length) {
    erroreDiario.value = 'Scegli almeno un destinatario.'
    return
  }
  try {
    const r = await api.post<{ detail: string }>(`/notifiche/diari/${rigaInvio.value.diario_id}/inviti`, {
      ruoli: ruoliDiario.value,
    })
    dialogoDiario.value = false
    avvisi.mostra(r.detail)
    void elenco.esegui()
  } catch (e) {
    erroreDiario.value = e instanceof ErroreApi ? messaggioErrore(e.message, e.errori) : 'Invio non riuscito.'
  }
}

// --- Reinvio -------------------------------------------------------------------------------------
function etichettaReinvio(r: RigaInviti, id: number): string {
  if (r.ultimo_invito_csq?.id === id) return 'Reinvia al Capo Squadriglia'
  if (r.ultimo_invito_crp?.id === id) return 'Reinvia al Capo Reparto'
  return `Reinvia l'invito n. ${id}`
}

async function reinvia(r: RigaInviti, id: number): Promise<void> {
  const ok = await conferma(`${etichettaReinvio(r, id)} di ${r.squadriglia}? Il link precedente non funzionerà più.`, {
    titolo: 'Reinvia invito',
    testoConferma: 'Reinvia',
  })
  if (!ok) return
  try {
    const esito = await api.post<{ detail: string }>(`/notifiche/inviti/${id}/reinvia`)
    avvisi.mostra(esito.detail)
    void elenco.esegui()
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Reinvio non riuscito.', 'danger')
  }
}

onMounted(() => {
  void riepilogo.esegui()
  void elenco.esegui()
})
</script>

<template>
  <h1 class="h3 mb-1">Gestione inviti</h1>
  <p v-if="riepilogo.dati.value?.edizione" class="fg-2 mb-6">{{ riepilogo.dati.value.edizione.nome }}</p>

  <StatoCaricamento :in-corso="riepilogo.inCorso.value && !riepilogo.dati.value" :errore="riepilogo.errore.value" @riprova="riepilogo.esegui">
    <template v-if="riepilogo.dati.value">
      <div v-if="!riepilogo.dati.value.edizione" class="alert theme-warning mt-6" role="status">
        Nessuna edizione attiva. Apri o crea un'edizione prima di inviare gli inviti.
        <RouterLink to="/edizioni">Vai alle edizioni</RouterLink>
      </div>

      <template v-else>
        <div class="grid mb-7">
          <section
            v-for="tipo in (['capi', 'csq'] as const)"
            :key="tipo"
            class="card g-col-12 md:g-col-6"
            :aria-labelledby="`titolo-invio-${tipo}`"
          >
            <div class="card-body d-flex flex-column">
              <h2 :id="`titolo-invio-${tipo}`" class="h5">
                <IconaBs :nome="tipo === 'capi' ? 'person-lines-fill' : 'people-fill'" class="me-2" />
                {{ tipo === 'capi' ? 'Capi Reparto' : 'Capi Squadriglia' }}
              </h2>
              <dl class="d-flex justify-content-between text-center mb-5">
                <div>
                  <dt class="small fg-2 fw-normal">Totale</dt>
                  <dd class="fs-3 fw-bold mb-0">{{ riepilogo.dati.value.contatori?.[`${tipo}_totale`] ?? 0 }}</dd>
                </div>
                <div>
                  <dt class="small fg-2 fw-normal">Da invitare</dt>
                  <dd class="fs-3 fw-bold mb-0 text-warning">{{ riepilogo.dati.value.contatori?.[`${tipo}_da_invitare`] ?? 0 }}</dd>
                </div>
                <div>
                  <dt class="small fg-2 fw-normal">Invitati</dt>
                  <dd class="fs-3 fw-bold mb-0 text-primary">{{ riepilogo.dati.value.contatori?.[`${tipo}_inviati`] ?? 0 }}</dd>
                </div>
                <div>
                  <dt class="small fg-2 fw-normal">Attivati</dt>
                  <dd class="fs-3 fw-bold mb-0 text-success">{{ riepilogo.dati.value.contatori?.[`${tipo}_attivati`] ?? 0 }}</dd>
                </div>
              </dl>
              <label :for="`canale-${tipo}`" class="form-label small">Canale di invio</label>
              <select :id="`canale-${tipo}`" v-model="canale[tipo]" class="form-control form-control-sm mb-4">
                <option value="massivo">Predefinito ({{ riepilogo.dati.value.backend_massivo_display }})</option>
                <option value="standard">Standard (email di sistema)</option>
              </select>
              <button
                type="button"
                class="btn btn-solid w-100 mt-auto"
                :class="tipo === 'capi' ? 'theme-primary' : 'theme-success'"
                :disabled="!riepilogo.dati.value.contatori?.[`${tipo}_da_invitare`] || inviando === tipo"
                @click="inviaEdizione(tipo)"
              >
                <IconaBs nome="send" class="me-2" />Invia inviti ai {{ tipo === 'capi' ? 'Capi Reparto' : 'Capi Squadriglia' }}
                <span v-if="riepilogo.dati.value.contatori?.[`${tipo}_da_invitare`]" class="badge theme-secondary ms-2">
                  {{ riepilogo.dati.value.contatori[`${tipo}_da_invitare`] }}
                </span>
              </button>
              <p v-if="tipo === 'csq'" class="fg-2 small mt-4 mb-0">
                <IconaBs nome="info-circle" class="me-1" />Il link di accesso viene consegnato ai Capi Reparto, che lo
                condividono con i propri Capi Squadriglia. Come canale secondario parte anche un'email diretta al Capo
                Squadriglia, se disponibile.
              </p>
            </div>
          </section>
        </div>

        <h2 class="h5 mb-4">Dettaglio per squadriglia</h2>
        <form class="d-flex flex-wrap align-items-end gap-4 mb-5" role="search" @submit.prevent>
          <div class="flex-grow-1" style="min-width: min(100%, 16rem)">
            <label for="inviti-q" class="form-label small">Cerca Capo Reparto o Capo Squadriglia</label>
            <input id="inviti-q" v-model="q" type="search" class="form-control" placeholder="Cognome o nome…" autocomplete="off" />
          </div>
          <div style="min-width: min(100%, 12rem)">
            <label for="inviti-zona" class="form-label small">Zona</label>
            <select id="inviti-zona" v-model="zona" class="form-control">
              <option value="">Tutte le zone</option>
              <option v-for="z in riepilogo.dati.value.zone" :key="z" :value="z">{{ z }}</option>
            </select>
          </div>
          <div style="min-width: min(100%, 12rem)">
            <label for="inviti-gruppo" class="form-label small">Gruppo</label>
            <select id="inviti-gruppo" v-model="gruppo" class="form-control">
              <option value="">Tutti i gruppi</option>
              <option v-for="g in riepilogo.dati.value.gruppi" :key="g" :value="g">{{ g }}</option>
            </select>
          </div>
          <div>
            <button type="button" class="btn btn-outline theme-secondary" :disabled="!filtriAttivi" @click="azzera">
              <IconaBs nome="x-circle" class="me-1" />Azzera filtri
            </button>
          </div>
        </form>

        <StatoCaricamento
          :in-corso="elenco.inCorso.value && !elenco.dati.value"
          :errore="elenco.errore.value"
          :vuoto="elenco.dati.value?.count === 0"
          :messaggio-vuoto="filtriAttivi ? 'Nessuna riga corrisponde ai filtri selezionati.' : 'Nessun diario trovato per questa edizione.'"
          @riprova="elenco.esegui"
        >
          <div v-if="elenco.dati.value" class="table-card table-responsive" :aria-busy="elenco.inCorso.value">
            <table class="table table-sm md:table-stacked align-middle">
              <thead>
                <tr>
                  <th scope="col" :aria-sort="ariaSort('squadriglia')">
                    <button type="button" class="btn btn-text btn-sm p-0 fw-semibold" @click="ordina('squadriglia')">
                      Squadriglia <IconaBs nome="chevron-expand" class="ms-1" />
                    </button>
                  </th>
                  <th scope="col" :aria-sort="ariaSort('csq')">
                    <button type="button" class="btn btn-text btn-sm p-0 fw-semibold" @click="ordina('csq')">
                      Capo Squadriglia <IconaBs nome="chevron-expand" class="ms-1" />
                    </button>
                  </th>
                  <th scope="col" :aria-sort="ariaSort('crp')">
                    <button type="button" class="btn btn-text btn-sm p-0 fw-semibold" @click="ordina('crp')">
                      Capo Reparto <IconaBs nome="chevron-expand" class="ms-1" />
                    </button>
                  </th>
                  <th scope="col">Invito Capo Squadriglia</th>
                  <th scope="col">Invito Capo Reparto</th>
                  <th scope="col"><span class="visually-hidden">Azioni</span></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in righe" :key="r.diario_id">
                  <td data-cell="Squadriglia">
                    <span class="fw-semibold">{{ r.squadriglia }}</span><br />
                    <small class="fg-2">{{ r.zona }} · {{ r.gruppo }} · {{ r.reparto }}</small>
                  </td>
                  <td data-cell="Capo Squadriglia">
                    <template v-if="r.csq">
                      {{ r.csq.cognome }} {{ r.csq.nome }}<br />
                      <small v-if="r.csq.email" class="fg-2 text-break">{{ r.csq.email }}</small>
                      <small v-else class="text-warning"><IconaBs nome="exclamation-triangle" class="me-1" />Email non disponibile</small>
                    </template>
                    <span v-else class="fg-2">—</span>
                  </td>
                  <td data-cell="Capo Reparto">
                    <template v-if="r.crp">
                      {{ r.crp.cognome }} {{ r.crp.nome }}<br />
                      <small v-if="r.crp.provvisorio" class="text-warning"><IconaBs nome="clock" class="me-1" />Da riconciliare</small>
                      <small v-else class="fg-2 text-break">{{ r.crp.email ?? '' }}</small>
                    </template>
                    <span v-else class="text-danger">Mancante</span>
                  </td>
                  <td data-cell="Invito Capo Squadriglia"><InvitiBadgeInvito :invito="r.ultimo_invito_csq" /></td>
                  <td data-cell="Invito Capo Reparto"><InvitiBadgeInvito :invito="r.ultimo_invito_crp" /></td>
                  <td class="text-end">
                    <div class="d-flex flex-wrap justify-content-end gap-2">
                      <button
                        v-for="id in r.inviti_reinviabili"
                        :key="id"
                        type="button"
                        class="btn btn-outline btn-sm theme-secondary"
                        :title="etichettaReinvio(r, id)"
                        @click="reinvia(r, id)"
                      >
                        <IconaBs nome="arrow-clockwise" />
                        <span class="visually-hidden">{{ etichettaReinvio(r, id) }} di {{ r.squadriglia }}</span>
                      </button>
                      <button
                        type="button"
                        class="btn btn-outline btn-sm theme-primary"
                        title="Invia gli inviti mancanti"
                        @click="apriInvioDiario(r)"
                      >
                        <IconaBs nome="send" />
                        <span class="visually-hidden">Invia gli inviti mancanti di {{ r.squadriglia }}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <PaginazioneElenco
            v-if="elenco.dati.value"
            v-model:offset="offset"
            :totale="elenco.dati.value.count"
            :limite="LIMITE"
          />
        </StatoCaricamento>
      </template>
    </template>
  </StatoCaricamento>

  <FinestraDialogo v-model:aperta="dialogoDiario" :titolo="`Inviti di ${rigaInvio?.squadriglia ?? ''}`">
    <p class="mb-4">Invia un invito per questo diario a:</p>
    <div class="form-field mb-2">
      <input id="invio-diario-csq" v-model="ruoliDiario" class="check" type="checkbox" value="csq" />
      <label for="invio-diario-csq">Capo Squadriglia</label>
    </div>
    <div class="form-field mb-4">
      <input id="invio-diario-crp" v-model="ruoliDiario" class="check" type="checkbox" value="crp" />
      <label for="invio-diario-crp">Capo Reparto</label>
    </div>
    <p class="small fg-2 mb-0">
      Serve un account già collegato al socio. A chi ha già ricevuto un invito conviene "Reinvia", che
      invalida il link precedente.
    </p>
    <div v-if="erroreDiario" class="alert theme-danger mt-4 mb-0" role="alert">{{ erroreDiario }}</div>
    <template #piede>
      <button type="button" class="btn btn-text theme-secondary" @click="dialogoDiario = false">Annulla</button>
      <button type="button" class="btn btn-solid theme-primary" @click="inviaDiario">
        <IconaBs nome="send" class="me-2" />Invia
      </button>
    </template>
  </FinestraDialogo>
</template>
