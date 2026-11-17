<script setup lang="ts">
import { useAvvisiStore } from '@/stores/avvisi'

const avvisi = useAvvisiStore()
</script>

<template>
  <div class="toast-container position-fixed bottom-0 end-0 p-5" aria-live="polite">
    <div
      v-for="a in avvisi.avvisi"
      :key="a.id"
      class="toast show"
      :class="`theme-${a.tipo}`"
      role="status"
    >
      <div class="toast-body d-flex align-items-center gap-3">
        <span>{{ a.testo }}</span>
        <button type="button" class="btn-close ms-auto" aria-label="Chiudi" @click="avvisi.chiudi(a.id)" />
      </div>
    </div>
  </div>
</template>
