<script setup lang="ts">
/** Scheda "Pagine statiche": privacy e termini (visualizza, carica predefinito, modifica). */
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import type { PaginaStatica } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { dataOra } from '@/composables/impostazioni-editor'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useRichiesta } from '@/composables/richiesta'

const elenco = useRichiesta(() => api.get<PaginaStatica[]>('/impostazioni/pagine'))
onMounted(elenco.esegui)
const importazione = useSalvataggio()

async function predefinito(p: PaginaStatica): Promise<void> {
  if (!(await conferma(`Sovrascrivere il contenuto attuale di «${p.slug_display}» con il testo predefinito?`, { testoConferma: 'Sovrascrivi', pericolosa: true }))) return
  if (await importazione.esegui(() => api.post(`/impostazioni/pagine/${p.slug}/importa`), 'Contenuto predefinito caricato.')) await elenco.esegui()
}
</script>

<template>
  <section class="card mb-6" aria-labelledby="titolo-pagine">
    <div class="card-body">
      <h2 id="titolo-pagine" class="h5 mb-4"><IconaBs nome="file-earmark-richtext" class="me-2" />Pagine legali</h2>
      <StatoCaricamento :in-corso="elenco.inCorso.value" :errore="elenco.errore.value" @riprova="elenco.esegui">
        <ul class="list-group">
          <li v-for="p in elenco.dati.value" :key="p.slug" class="list-group-item d-flex flex-wrap align-items-center gap-3 py-4">
            <div class="flex-grow-1">
              <strong>{{ p.slug_display }}</strong>
              <span class="small fg-2 ms-2">/pagine/{{ p.slug }}</span>
              <div class="small fg-2">
                {{ p.aggiornato_at ? `Aggiornata il ${dataOra(p.aggiornato_at)}` : 'Mai salvata: viene mostrato un segnaposto.' }}
              </div>
            </div>
            <div class="d-flex flex-wrap gap-2">
              <RouterLink :to="`/pagine/${p.slug}`" target="_blank" class="btn btn-outline btn-sm theme-secondary" :aria-label="`Visualizza ${p.slug_display} in una nuova scheda`">
                <IconaBs nome="box-arrow-up-right" class="me-1" />Visualizza
              </RouterLink>
              <button type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="importazione.inCorso.value" title="Carica il contenuto predefinito" @click="predefinito(p)">
                <IconaBs nome="download" class="me-1" />Predefinito
              </button>
              <RouterLink :to="`/impostazioni/pagine/${p.slug}`" class="btn btn-outline btn-sm theme-primary">
                <IconaBs nome="pencil" class="me-1" />Modifica
              </RouterLink>
            </div>
          </li>
        </ul>
      </StatoCaricamento>
    </div>
  </section>
</template>
