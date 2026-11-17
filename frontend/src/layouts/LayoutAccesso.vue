<script setup lang="ts">
// Layout delle pagine pubbliche (accesso, recupero password, attivazione): niente sidebar.
import { RouterView } from 'vue-router'

import PiePagina from '@/components/PiePagina.vue'
import { useSitoStore } from '@/stores/sito'
import emblema from '@/assets/EMBLEMA_CAMPANIA_WHITE.svg'

const sito = useSitoStore()
</script>

<template>
  <header class="ag-header-top px-5 py-3 d-flex align-items-center">
    <span class="ag-header-brand">
      <img :src="emblema" alt="" />
      <span>{{ sito.sito?.titolo ?? 'Plancia' }}</span>
    </span>
  </header>
  <div class="ag-scroll-area flex-grow-1">
    <main class="container py-7" style="max-width: 32rem">
      <div
        v-if="sito.sito?.manutenzione?.attiva"
        class="alert theme-danger"
        role="status"
      >
        {{ sito.sito.manutenzione.messaggio || 'Plancia è in manutenzione.' }}
      </div>
      <RouterView />
    </main>
    <PiePagina />
  </div>
</template>
