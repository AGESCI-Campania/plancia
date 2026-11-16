<script setup lang="ts">
/** Editor di una pagina statica (privacy, termini): titolo e contenuto HTML (Tiptap). */
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import ImpostazioniEditorHtml from '@/components/impostazioni/ImpostazioniEditorHtml.vue'
import type { PaginaStatica } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { dataOra } from '@/composables/impostazioni-editor'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useRichiesta } from '@/composables/richiesta'

const props = defineProps<{ slug: string }>()

// La lettura per slug è pubblica; per la modifica si usa l'elenco staff (stesso contenuto)
const pagina = useRichiesta(async () => {
  const pagine = await api.get<PaginaStatica[]>('/impostazioni/pagine')
  const p = pagine.find((x) => x.slug === props.slug)
  if (!p) throw new Error('Pagina non trovata.')
  return p
})
const titolo = ref('')
const contenuto = ref('')

function applica(p: PaginaStatica | null): void {
  if (!p) return
  titolo.value = p.titolo
  contenuto.value = p.contenuto
}
watch(() => props.slug, async () => applica(await pagina.esegui()), { immediate: true })

const salvataggio = useSalvataggio()
async function salva(): Promise<void> {
  const r = await salvataggio.esegui(
    () => api.put<PaginaStatica>(`/impostazioni/pagine/${props.slug}`, { titolo: titolo.value, contenuto: contenuto.value }),
    'Pagina salvata.',
  )
  if (r) {
    pagina.dati.value = r
    applica(r)
  }
}

async function predefinito(): Promise<void> {
  if (!(await conferma('Sovrascrivere il contenuto attuale con il testo predefinito?', { testoConferma: 'Sovrascrivi', pericolosa: true }))) return
  const r = await salvataggio.esegui(() => api.post<PaginaStatica>(`/impostazioni/pagine/${props.slug}/importa`), 'Contenuto predefinito caricato.')
  if (r) {
    pagina.dati.value = r
    applica(r)
  }
}
</script>

<template>
  <StatoCaricamento :in-corso="pagina.inCorso.value && !pagina.dati.value" :errore="pagina.errore.value" @riprova="pagina.esegui">
    <template v-if="pagina.dati.value">
      <div class="d-flex flex-wrap align-items-start gap-3 mb-5">
        <div class="flex-grow-1">
          <h1 class="h3 mb-1">{{ pagina.dati.value.slug_display }}</h1>
          <small class="fg-2">{{ pagina.dati.value.aggiornato_at ? `Aggiornata il ${dataOra(pagina.dati.value.aggiornato_at)}` : 'Mai salvata.' }}</small>
        </div>
        <div class="d-flex flex-wrap gap-2">
          <RouterLink :to="`/pagine/${slug}`" target="_blank" class="btn btn-outline btn-sm theme-secondary">
            <IconaBs nome="box-arrow-up-right" class="me-1" />Visualizza
          </RouterLink>
          <button type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="salvataggio.inCorso.value" @click="predefinito">
            <IconaBs nome="download" class="me-1" />Carica predefinito
          </button>
        </div>
      </div>
      <form class="card" novalidate @submit.prevent="salva">
        <div class="card-body">
          <CampoForm v-model="titolo" etichetta="Titolo" obbligatorio :errori="salvataggio.errori.value.titolo" />
          <ImpostazioniEditorHtml v-model="contenuto" etichetta="Contenuto" :errori="salvataggio.errori.value.contenuto" altezza="28rem" />
          <div class="d-flex justify-content-end gap-3">
            <RouterLink to="/impostazioni/pagine" class="btn btn-outline theme-secondary">Annulla</RouterLink>
            <button type="submit" class="btn btn-solid theme-primary" :disabled="salvataggio.inCorso.value">
              <IconaBs nome="check-lg" class="me-1" />Salva
            </button>
          </div>
        </div>
      </form>
    </template>
  </StatoCaricamento>
</template>
