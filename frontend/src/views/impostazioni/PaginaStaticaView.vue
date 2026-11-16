<script setup lang="ts">
/** Pagina pubblica (privacy, termini): contenuto HTML scritto dagli Admin nelle impostazioni. */
import { watch } from 'vue'

import { api } from '@/api/http'
import type { components } from '@/api/schema'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { dataOra } from '@/composables/impostazioni-editor'
import { useRichiesta } from '@/composables/richiesta'

type Pagina = components['schemas']['PaginaSchema']

const props = defineProps<{ slug: string }>()
const pagina = useRichiesta(() => api.get<Pagina>(`/sito/pagine/${props.slug}`))

watch(
  () => props.slug,
  async () => {
    const p = await pagina.esegui()
    if (p) document.title = `${p.titolo} · Plancia`
  },
  { immediate: true },
)
</script>

<template>
  <div class="row justify-content-center">
    <div class="lg:col-8">
      <StatoCaricamento :in-corso="pagina.inCorso.value" :errore="pagina.errore.value" @riprova="pagina.esegui">
        <article v-if="pagina.dati.value">
          <h1 class="h2 mb-5">{{ pagina.dati.value.titolo }}</h1>
          <!-- HTML scritto dagli Admin (stessa fiducia del |safe della vecchia pagina Django) -->
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="prose" v-html="pagina.dati.value.contenuto" />
          <p v-if="pagina.dati.value.aggiornato_at" class="small fg-2 mt-6">
            Ultimo aggiornamento: {{ dataOra(pagina.dati.value.aggiornato_at) }}
          </p>
        </article>
      </StatoCaricamento>
    </div>
  </div>
</template>
