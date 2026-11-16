<script setup lang="ts">
/** Apertura di un ticket: oggetto, categoria, descrizione e, se ce ne sono, un diario collegato. */
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { api, ErroreApi, type ErroriCampo } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { messaggioErrore } from '@/components/utenti/formato'
import type { OpzioniTicket, TicketDettaglio } from '@/components/utenti/tipi'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const CAMPI = ['oggetto', 'corpo', 'categoria', 'diario']
const router = useRouter()
const avvisi = useAvvisiStore()
const opzioni = useRichiesta(() => api.get<OpzioniTicket>('/helpdesk/opzioni'))

const oggetto = ref('')
const categoria = ref('')
const corpo = ref('')
const diario = ref('')
const errori = ref<ErroriCampo>({})
const errore = ref('')
const inCorso = ref(false)

async function invia(): Promise<void> {
  errore.value = ''
  const locali: ErroriCampo = {}
  if (!oggetto.value.trim()) locali.oggetto = ['Scrivi l’oggetto.']
  if (!categoria.value) locali.categoria = ['Scegli la categoria.']
  if (!corpo.value.trim()) locali.corpo = ['Descrivi il problema.']
  errori.value = locali
  if (Object.keys(locali).length) return
  inCorso.value = true
  try {
    const t = await api.post<TicketDettaglio>('/helpdesk', {
      oggetto: oggetto.value.trim(),
      corpo: corpo.value.trim(),
      categoria: categoria.value,
      diario_id: diario.value ? Number(diario.value) : null,
    })
    avvisi.mostra('Ticket aperto con successo.')
    await router.push(`/helpdesk/${t.id}`)
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = e.errori
      errore.value = messaggioErrore(e.message, e.errori, CAMPI)
    } else errore.value = 'Errore imprevisto.'
  } finally {
    inCorso.value = false
  }
}

onMounted(opzioni.esegui)
</script>

<template>
  <div style="max-width: 40rem">
    <h1 class="h3 mb-6">Apri un ticket di assistenza</h1>
    <StatoCaricamento :in-corso="opzioni.inCorso.value" :errore="opzioni.errore.value" @riprova="opzioni.esegui">
      <form v-if="opzioni.dati.value" novalidate @submit.prevent="invia">
        <div v-if="errore" class="alert theme-danger" role="alert">{{ errore }}</div>
        <CampoForm v-model="oggetto" etichetta="Oggetto" obbligatorio :errori="errori.oggetto" />
        <div class="mb-5">
          <label for="ticket-categoria" class="form-label">Categoria</label>
          <select
            id="ticket-categoria"
            v-model="categoria"
            class="form-control"
            :class="{ 'is-invalid': errori.categoria?.length }"
            required
          >
            <option value="" disabled>Scegli…</option>
            <option v-for="c in opzioni.dati.value.categorie" :key="c.chiave" :value="c.chiave">{{ c.etichetta }}</option>
          </select>
          <div v-for="e in errori.categoria ?? []" :key="e" class="invalid-feedback">{{ e }}</div>
        </div>
        <div class="mb-5">
          <label for="ticket-corpo" class="form-label">Descrizione</label>
          <textarea
            id="ticket-corpo"
            v-model="corpo"
            class="form-control"
            :class="{ 'is-invalid': errori.corpo?.length }"
            rows="6"
            required
          />
          <div v-for="e in errori.corpo ?? []" :key="e" class="invalid-feedback">{{ e }}</div>
        </div>
        <div v-if="opzioni.dati.value.diari.length" class="mb-5">
          <label for="ticket-diario" class="form-label">Diario collegato (facoltativo)</label>
          <select
            id="ticket-diario"
            v-model="diario"
            class="form-control"
            :class="{ 'is-invalid': errori.diario?.length }"
          >
            <option value="">Nessuno</option>
            <option v-for="d in opzioni.dati.value.diari" :key="d.id" :value="String(d.id)">
              {{ d.squadriglia }} · {{ d.edizione_anno }}
            </option>
          </select>
          <div v-for="e in errori.diario ?? []" :key="e" class="invalid-feedback">{{ e }}</div>
        </div>
        <div class="d-flex gap-3">
          <button type="submit" class="btn btn-solid theme-primary" :disabled="inCorso">Apri ticket</button>
          <RouterLink to="/helpdesk" class="btn btn-outline theme-secondary">Annulla</RouterLink>
        </div>
      </form>
    </StatoCaricamento>
  </div>
</template>
