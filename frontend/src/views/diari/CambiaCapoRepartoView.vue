<script setup lang="ts">
/**
 * Cambio del Capo Reparto per tutti i diari non ancora inviati di un reparto (staff):
 * `GET`/`POST /diari/reparti/{id}/cambia-crp`. Il backend decide chi può e quali diari tocca.
 */
import { ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import BadgeStato from '@/components/BadgeStato.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import DiariSelettoreSocio from '@/components/diari/DiariSelettoreSocio.vue'
import {
  nomeReferente,
  type RepartoDiari,
  type RispostaCambioCrpReparto,
  type Socio,
} from '@/components/diari/diari'
import { conferma } from '@/composables/conferma'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ id: number }>()
const router = useRouter()
const avvisi = useAvvisiStore()

const richiesta = useRichiesta(() => api.get<RepartoDiari>(`/diari/reparti/${props.id}/cambia-crp`))
watch(
  () => props.id,
  async () => {
    const r = await richiesta.esegui()
    if (r) document.title = `Cambia Capo Reparto — ${r.reparto.nome} · Plancia`
  },
  { immediate: true },
)

const socio = ref<Socio | null>(null)
const errori = ref<string[]>([])
const inCorso = ref(false)

async function invia(): Promise<void> {
  errori.value = []
  const dati = richiesta.dati.value
  if (!socio.value || !dati) {
    errori.value = ['Scegli il nuovo Capo Reparto.']
    return
  }
  const n = dati.diari.length
  const ok = await conferma(
    `Assegnare ${socio.value.label} come Capo Reparto a ${n === 1 ? '1 diario' : `${n} diari`} del reparto ${dati.reparto.nome}?`,
    { titolo: 'Cambia Capo Reparto', testoConferma: 'Conferma cambio' },
  )
  if (!ok) return
  inCorso.value = true
  try {
    const r = await api.post<RispostaCambioCrpReparto>(`/diari/reparti/${props.id}/cambia-crp`, {
      socio_id: socio.value.id,
    })
    avvisi.mostra(r.detail)
    await router.push('/diari')
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = Object.values(e.errori).flat()
      if (!errori.value.length) errori.value = [e.message]
    } else {
      errori.value = ['Operazione non riuscita.']
    }
  } finally {
    inCorso.value = false
  }
}
</script>

<template>
  <div class="plancia-diari-stretto">
    <StatoCaricamento
      :in-corso="richiesta.inCorso.value"
      :errore="richiesta.errore.value"
      @riprova="richiesta.esegui"
    >
      <template v-if="richiesta.dati.value">
        <h1 class="h3 mb-5">Cambia Capo Reparto — {{ richiesta.dati.value.reparto.nome }}</h1>

        <template v-if="richiesta.dati.value.diari.length">
          <p class="fg-2">
            Il nuovo Capo Reparto verrà assegnato a
            <strong
              >{{ richiesta.dati.value.diari.length }}
              {{ richiesta.dati.value.diari.length === 1 ? 'diario' : 'diari' }}</strong
            >
            non ancora inviati di questo reparto.
          </p>

          <section class="card mb-6" aria-labelledby="titolo-coinvolti">
            <div class="card-header">
              <h2 id="titolo-coinvolti" class="h6 mb-0">Diari coinvolti</h2>
            </div>
            <ul class="list-group list-group-flush">
              <li
                v-for="d in richiesta.dati.value.diari"
                :key="d.id"
                class="list-group-item d-flex flex-wrap align-items-center gap-3"
              >
                <span class="flex-grow-1">
                  <RouterLink :to="`/diari/${d.id}`" class="fw-semibold">{{
                    d.squadriglia
                  }}</RouterLink>
                  <small class="fg-2 ms-2">Edizione {{ d.edizione_anno }}</small>
                </span>
                <BadgeStato :stato="d.stato" :etichetta="d.stato_display" />
                <small class="fg-2 w-100 md:w-auto"
                  >Capo Reparto attuale: {{ nomeReferente(d.crp) || '—' }}</small
                >
              </li>
            </ul>
          </section>

          <form novalidate @submit.prevent="invia">
            <DiariSelettoreSocio
              v-model="socio"
              etichetta="Nuovo Capo Reparto"
              categoria="capo"
              aiuto="Digita almeno 2 caratteri per cercare tra i capi."
              :errori="errori"
            />
            <div class="d-flex flex-wrap gap-3">
              <button type="submit" class="btn btn-solid theme-primary" :disabled="inCorso">
                <span
                  v-if="inCorso"
                  class="spinner-border spinner-sm me-2"
                  aria-hidden="true"
                />Conferma cambio per tutti i diari
              </button>
              <RouterLink to="/diari" class="btn btn-outline theme-secondary">Annulla</RouterLink>
            </div>
          </form>
        </template>

        <template v-else>
          <div class="alert theme-info" role="status">
            Nessun diario non ancora inviato per questo reparto. Nessuna modifica necessaria.
          </div>
          <RouterLink to="/diari" class="btn btn-outline btn-sm theme-secondary">
            <IconaBs nome="arrow-left" class="me-2" />Torna ai diari
          </RouterLink>
        </template>
      </template>
    </StatoCaricamento>
  </div>
</template>

<style scoped>
.plancia-diari-stretto {
  max-width: 44rem;
}
</style>
