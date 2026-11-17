<script setup lang="ts">
/**
 * Impostazioni della piattaforma (solo Admin), a schede: ogni scheda ha il suo percorso
 * (`/impostazioni/email`…), così la callback di Gmail OAuth (`?esito=ok|errore&messaggio=`)
 * torna direttamente sulla scheda giusta.
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import SchedaEmail from '@/components/impostazioni/SchedaEmail.vue'
import SchedaGenerale from '@/components/impostazioni/SchedaGenerale.vue'
import SchedaPagine from '@/components/impostazioni/SchedaPagine.vue'
import SchedaSicurezza from '@/components/impostazioni/SchedaSicurezza.vue'
import SchedaSistema from '@/components/impostazioni/SchedaSistema.vue'
import SchedaTemplateEmail from '@/components/impostazioni/SchedaTemplateEmail.vue'
import type { Impostazioni } from '@/components/impostazioni/tipi'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const SCHEDE = [
  { chiave: 'generale', etichetta: 'Identità e footer', icona: 'card-heading' },
  { chiave: 'email', etichetta: 'Posta elettronica', icona: 'envelope' },
  { chiave: 'sicurezza', etichetta: 'Sicurezza', icona: 'shield-lock' },
  { chiave: 'sistema', etichetta: 'Sistema', icona: 'sliders' },
  { chiave: 'template-email', etichetta: 'Template email', icona: 'file-earmark-text' },
  { chiave: 'pagine', etichetta: 'Pagine legali', icona: 'file-earmark-richtext' },
] as const

const route = useRoute()
const router = useRouter()
const avvisi = useAvvisiStore()

const scheda = computed(() => (route.params.scheda as string | undefined) || 'generale')
const impostazioni = useRichiesta(() => api.get<Impostazioni>('/impostazioni'))
onMounted(impostazioni.esegui)

// Su schermi stretti le schede scorrono: quella attiva va portata in vista
const schede = ref<HTMLElement>()
watch(
  scheda,
  async () => {
    await nextTick()
    schede.value?.querySelector('.nav-link.active')?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
  },
  { immediate: true },
)

function aggiornate(nuove: Impostazioni): void {
  impostazioni.dati.value = nuove
}

// Esito della callback Gmail OAuth: avviso e pulizia dell'URL
watch(
  () => route.query.esito,
  (esito) => {
    if (!esito) return
    const messaggio = String(route.query.messaggio ?? '')
    if (esito === 'ok') avvisi.mostra(messaggio || 'Account Gmail collegato.', 'success', 8000)
    else avvisi.mostra(messaggio || 'Collegamento non riuscito.', 'danger', 10000)
    void router.replace({ path: route.path, query: {} })
    void impostazioni.esegui()
  },
  { immediate: true },
)
</script>

<template>
  <div class="d-flex flex-wrap align-items-end gap-3 mb-5">
    <h1 class="h3 mb-0">Impostazioni della piattaforma</h1>
  </div>

  <nav ref="schede" class="impostazioni-schede mb-6" aria-label="Sezioni delle impostazioni">
    <ul class="nav nav-underline flex-nowrap">
      <li v-for="s in SCHEDE" :key="s.chiave" class="nav-item">
        <RouterLink
          :to="s.chiave === 'generale' ? '/impostazioni' : `/impostazioni/${s.chiave}`"
          class="nav-link text-nowrap"
          :class="{ active: scheda === s.chiave }"
          :aria-current="scheda === s.chiave ? 'page' : undefined"
        >
          <IconaBs :nome="s.icona" class="me-2" />{{ s.etichetta }}
        </RouterLink>
      </li>
    </ul>
  </nav>

  <StatoCaricamento
    v-if="scheda !== 'template-email' && scheda !== 'pagine'"
    :in-corso="impostazioni.inCorso.value && !impostazioni.dati.value"
    :errore="impostazioni.errore.value"
    @riprova="impostazioni.esegui"
  >
    <template v-if="impostazioni.dati.value">
      <SchedaGenerale v-if="scheda === 'generale'" :dati="impostazioni.dati.value" @aggiornate="aggiornate" />
      <SchedaEmail v-else-if="scheda === 'email'" :dati="impostazioni.dati.value" @aggiornate="aggiornate" />
      <SchedaSicurezza v-else-if="scheda === 'sicurezza'" :dati="impostazioni.dati.value" @aggiornate="aggiornate" />
      <SchedaSistema v-else-if="scheda === 'sistema'" :dati="impostazioni.dati.value" @aggiornate="aggiornate" />
    </template>
  </StatoCaricamento>
  <SchedaTemplateEmail v-else-if="scheda === 'template-email'" />
  <SchedaPagine v-else />
</template>

<style scoped>
.impostazioni-schede {
  overflow-x: auto;
  scrollbar-width: thin;
}
</style>
