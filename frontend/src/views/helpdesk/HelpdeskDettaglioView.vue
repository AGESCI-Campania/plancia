<script setup lang="ts">
/**
 * Dettaglio di un ticket: dati, descrizione, risposte e le azioni consentite secondo l'API
 * (`azioni`: rispondi, prendi in carico, chiudi).
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import HelpdeskBadgeStato from '@/components/helpdesk/HelpdeskBadgeStato.vue'
import { dataOra, messaggioErrore } from '@/components/utenti/formato'
import type { TicketDettaglio } from '@/components/utenti/tipi'
import { conferma } from '@/composables/conferma'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ id: number }>()
const avvisi = useAvvisiStore()
const ticket = useRichiesta(() => api.get<TicketDettaglio>(`/helpdesk/${props.id}`))
const t = computed(() => ticket.dati.value)

watch(t, (dati) => {
  if (dati) document.title = `Ticket #${dati.id} · Plancia`
})

const testo = ref('')
const erroriTesto = ref<string[]>([])
const inCorso = ref(false)

async function esegui(operazione: () => Promise<unknown>, successo: string): Promise<boolean> {
  inCorso.value = true
  try {
    await operazione()
    avvisi.mostra(successo)
    await ticket.esegui()
    return true
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? messaggioErrore(e.message, e.errori) : 'Operazione non riuscita.', 'danger')
    return false
  } finally {
    inCorso.value = false
  }
}

async function rispondi(): Promise<void> {
  erroriTesto.value = []
  if (!testo.value.trim()) {
    erroriTesto.value = ['Scrivi la risposta.']
    return
  }
  inCorso.value = true
  try {
    await api.post(`/helpdesk/${props.id}/risposte`, { testo: testo.value.trim() })
    testo.value = ''
    avvisi.mostra('Risposta aggiunta.')
    await ticket.esegui()
  } catch (e) {
    if (e instanceof ErroreApi && e.errori.testo) erroriTesto.value = e.errori.testo
    else avvisi.mostra(e instanceof ErroreApi ? messaggioErrore(e.message, e.errori) : 'Risposta non inviata.', 'danger')
  } finally {
    inCorso.value = false
  }
}

function prendiInCarico(): void {
  void esegui(() => api.post(`/helpdesk/${props.id}/prendi-in-carico`), 'Ticket preso in carico.')
}

async function chiudi(): Promise<void> {
  const ok = await conferma('Chiudere il ticket? Non si potranno più aggiungere risposte.', {
    titolo: 'Chiudi ticket',
    testoConferma: 'Chiudi ticket',
    pericolosa: true,
  })
  if (ok) await esegui(() => api.post(`/helpdesk/${props.id}/chiudi`), 'Ticket chiuso.')
}

watch(
  () => props.id,
  () => void ticket.esegui(),
)
onMounted(ticket.esegui)
</script>

<template>
  <StatoCaricamento :in-corso="ticket.inCorso.value && !t" :errore="t ? '' : ticket.errore.value" @riprova="ticket.esegui">
    <template v-if="t">
      <div class="d-flex flex-wrap align-items-center gap-3 mb-6">
        <RouterLink to="/helpdesk" class="btn btn-subtle btn-sm theme-secondary" aria-label="Torna all'helpdesk">
          <IconaBs nome="arrow-left" />
        </RouterLink>
        <h1 class="h4 mb-0">Ticket #{{ t.id }}: {{ t.oggetto }}</h1>
        <HelpdeskBadgeStato :stato="t.stato" :etichetta="t.stato_display" />
      </div>

      <section class="card mb-6" aria-label="Richiesta">
        <div class="card-body">
          <dl class="mb-5">
            <dt>Aperto da</dt>
            <dd>{{ t.aperto_da.nome }} · {{ dataOra(t.creato_at) }}</dd>
            <dt>Categoria</dt>
            <dd>{{ t.categoria_display }}</dd>
            <template v-if="t.diario">
              <dt>Diario</dt>
              <dd><RouterLink :to="`/diari/${t.diario.id}`">{{ t.diario.squadriglia }} · {{ t.diario.edizione_anno }}</RouterLink></dd>
            </template>
            <template v-if="t.assegnato_a">
              <dt>Assegnato a</dt>
              <dd>{{ t.assegnato_a.nome }}</dd>
            </template>
          </dl>
          <hr />
          <p class="mb-0" style="white-space: pre-line">{{ t.corpo }}</p>
        </div>
      </section>

      <h2 v-if="t.risposte.length" class="h5 mb-4">Risposte</h2>
      <ol class="list-unstyled mb-6">
        <li
          v-for="r in t.risposte"
          :key="r.id"
          class="card mb-3"
          :class="{ 'border-primary': r.autore.id === t.aperto_da.id }"
          :style="r.autore.id === t.aperto_da.id ? 'border-inline-start-width: 3px' : undefined"
        >
          <div class="card-body py-3">
            <small class="fg-2">{{ r.autore.nome }} · {{ dataOra(r.creata_at) }}</small>
            <p class="mb-0 mt-1" style="white-space: pre-line">{{ r.testo }}</p>
          </div>
        </li>
      </ol>

      <form v-if="t.azioni.rispondi" class="mb-5" novalidate @submit.prevent="rispondi">
        <label for="ticket-risposta" class="form-label">La tua risposta</label>
        <textarea
          id="ticket-risposta"
          v-model="testo"
          class="form-control mb-3"
          :class="{ 'is-invalid': erroriTesto.length }"
          rows="4"
          placeholder="Scrivi una risposta…"
          required
        />
        <div v-for="e in erroriTesto" :key="e" class="invalid-feedback mb-3">{{ e }}</div>
        <button type="submit" class="btn btn-solid theme-primary" :disabled="inCorso">
          <IconaBs nome="reply" class="me-2" />Rispondi
        </button>
      </form>

      <div v-if="t.azioni.prendi_in_carico || t.azioni.chiudi" class="d-flex flex-wrap gap-3">
        <button
          v-if="t.azioni.prendi_in_carico"
          type="button"
          class="btn btn-outline theme-secondary"
          :disabled="inCorso"
          @click="prendiInCarico"
        >
          <IconaBs nome="person-check" class="me-2" />Prendi in carico
        </button>
        <button v-if="t.azioni.chiudi" type="button" class="btn btn-outline theme-danger" :disabled="inCorso" @click="chiudi">
          <IconaBs nome="x-circle" class="me-2" />Chiudi ticket
        </button>
      </div>

      <div v-if="t.stato === 'chiuso'" class="alert theme-secondary" role="status">
        Ticket chiuso il {{ dataOra(t.chiuso_at) }}.
      </div>
    </template>
  </StatoCaricamento>
</template>
