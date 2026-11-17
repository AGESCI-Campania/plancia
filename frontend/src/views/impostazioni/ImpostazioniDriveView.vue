<script setup lang="ts">
/**
 * Google Drive: stato del collegamento OAuth e account autorizzati, avvio del collegamento.
 * È anche la destinazione della callback OAuth partita da qui (`?esito=ok|errore&messaggio=`).
 * Le cartelle di ogni edizione si configurano dalla pagina dell'edizione.
 */
import { onMounted, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import type { StatoDrive } from '@/components/impostazioni/tipi'
import { dataOra } from '@/composables/impostazioni-editor'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const route = useRoute()
const router = useRouter()
const avvisi = useAvvisiStore()
const stato = useRichiesta(() => api.get<StatoDrive>('/drive/stato'))
onMounted(stato.esegui)

watch(
  () => route.query.esito,
  (esito) => {
    if (!esito) return
    const messaggio = String(route.query.messaggio ?? '')
    if (esito === 'ok') avvisi.mostra(messaggio || 'Account Google Drive collegato.', 'success', 8000)
    else avvisi.mostra(messaggio || 'Collegamento a Google Drive non riuscito.', 'danger', 10000)
    void router.replace({ path: route.path, query: {} })
  },
  { immediate: true },
)

const avvio = useSalvataggio()
async function collega(): Promise<void> {
  const r = await avvio.esegui(() => api.post<{ url: string }>('/drive/oauth', {}))
  if (r?.url) window.location.assign(r.url)
}
</script>

<template>
  <h1 class="h3 mb-5">Google Drive</h1>
  <StatoCaricamento :in-corso="stato.inCorso.value" :errore="stato.errore.value" @riprova="stato.esegui">
    <template v-if="stato.dati.value">
      <section class="card mb-6" aria-labelledby="titolo-drive">
        <div class="card-body">
          <h2 id="titolo-drive" class="h5 mb-4"><IconaBs nome="cloud-check" class="me-2" />Collegamento</h2>
          <div v-if="!stato.dati.value.oauth_configurato" class="alert theme-warning" role="alert">
            <IconaBs nome="exclamation-triangle" class="me-2" />Il client OAuth di Google non è configurato sul
            server (variabili d'ambiente): il collegamento a Drive non è disponibile.
          </div>
          <p class="small fg-2">
            Gli account collegati servono a caricare allegati e PDF dei diari nelle cartelle Drive delle
            edizioni. Le cartelle di ogni edizione si scelgono dalla pagina dell'edizione.
          </p>
          <button
            type="button"
            class="btn btn-solid theme-primary"
            :disabled="!stato.dati.value.oauth_configurato || avvio.inCorso.value"
            @click="collega"
          >
            <IconaBs nome="google" class="me-1" />Collega un account Google Drive
          </button>
        </div>
      </section>

      <section class="card mb-6" aria-labelledby="titolo-account-drive">
        <div class="card-body">
          <h2 id="titolo-account-drive" class="h5 mb-4">Account collegati</h2>
          <p v-if="!stato.dati.value.account.length" class="fg-2 mb-0">Nessun account collegato.</p>
          <ul v-else class="list-group">
            <li v-for="a in stato.dati.value.account" :key="a.email" class="list-group-item d-flex flex-wrap align-items-center gap-3">
              <span class="fw-semibold text-break">{{ a.email }}</span>
              <span v-if="a.token_scaduto" class="badge theme-danger">Autorizzazione scaduta</span>
              <span v-else class="badge theme-success">Attivo</span>
              <span class="small fg-2 ms-auto">Aggiornato il {{ dataOra(a.aggiornato_at) }}</span>
            </li>
          </ul>
          <p v-if="stato.dati.value.account.some((a) => a.token_scaduto)" class="small fg-2 mt-3 mb-0">
            Per un account con l'autorizzazione scaduta ripeti il collegamento con lo stesso account.
          </p>
        </div>
      </section>
      <RouterLink to="/edizioni" class="btn btn-text theme-secondary"><IconaBs nome="arrow-left" class="me-1" />Edizioni</RouterLink>
    </template>
  </StatoCaricamento>
</template>
