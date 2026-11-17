<script setup lang="ts">
/**
 * Footer: testi e link da Impostazioni (via `/api/v1/sito`), più le versioni dell'app
 * installata e del server; se l'app è indietro, il pulsante Aggiorna.
 */
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import IconaBs from '@/components/IconaBs.vue'
import { aggiornaOra, needRefresh, versioneInferiore } from '@/pwa/aggiornamento'
import { useSitoStore } from '@/stores/sito'
import emblema from '@/assets/EMBLEMA_CAMPANIA_WHITE.svg'

const sito = useSitoStore()
const versioneApp = __VERSIONE_APP__
const daAggiornare = computed(
  () => needRefresh.value || versioneInferiore(versioneApp, sito.versioneServer),
)

const footer = computed(() => sito.sito?.footer)
const anno = new Date().getFullYear()
</script>

<template>
  <footer class="ag-footer py-5">
    <div class="container">
      <div class="row g-5 align-items-center">
        <div class="col-12 md:col-3">
          <img :src="emblema" alt="AGESCI Campania" class="ag-footer__logo mb-2" />
          <p class="small mb-0">{{ sito.sito?.titolo ?? 'Plancia' }}</p>
        </div>
        <div v-if="footer?.links.length || footer?.manuale_url" class="col-6 md:col-3">
          <ul class="ag-footer__nav">
            <li v-for="link in footer?.links ?? []" :key="link.url">
              <a :href="link.url" target="_blank" rel="noopener">{{ link.etichetta }}</a>
            </li>
            <li v-if="footer?.manuale_url">
              <a :href="footer.manuale_url" target="_blank" rel="noopener">Manuale</a>
            </li>
            <li v-for="pagina in sito.sito?.pagine ?? []" :key="pagina.slug">
              <RouterLink :to="`/pagine/${pagina.slug}`">{{ pagina.titolo }}</RouterLink>
            </li>
          </ul>
        </div>
        <div class="col-12 md:col-auto md:ms-auto text-center md:text-end small">
          <!-- HTML reso dal backend dal testo scritto in Impostazioni (solo staff) -->
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-if="footer?.testo" class="mb-2" v-html="footer.testo" />
          <p class="mb-2">© {{ anno }} AGESCI Campania</p>
          <p class="mb-0 d-flex flex-wrap gap-2 justify-content-center md:justify-content-end">
            <span class="badge theme-secondary plancia-badge-versione" title="Versione dell'app installata">
              App v{{ versioneApp }}
            </span>
            <span
              v-if="sito.versioneServer"
              class="badge theme-secondary plancia-badge-versione"
              title="Versione installata sul server"
            >
              Server v{{ sito.versioneServer }}
            </span>
            <button
              v-if="daAggiornare"
              type="button"
              class="btn btn-solid btn-xs theme-warning"
              @click="aggiornaOra"
            >
              <IconaBs nome="arrow-repeat" class="me-1" />Aggiorna
            </button>
          </p>
        </div>
      </div>
    </div>
  </footer>
</template>
