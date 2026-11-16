<script setup lang="ts">
/** Paginazione per le liste `LimitOffsetPagination` di django-ninja (`v-model:offset`). */
import { computed } from 'vue'

const props = defineProps<{ totale: number; limite: number }>()
const offset = defineModel<number>('offset', { required: true })
const pagina = computed(() => Math.floor(offset.value / props.limite) + 1)
const pagine = computed(() => Math.max(1, Math.ceil(props.totale / props.limite)))

function vai(n: number): void {
  offset.value = (Math.min(Math.max(n, 1), pagine.value) - 1) * props.limite
}
</script>

<template>
  <nav v-if="pagine > 1" aria-label="Pagine" class="d-flex align-items-center gap-3 my-5">
    <button type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="pagina <= 1" @click="vai(pagina - 1)">
      Precedente
    </button>
    <span class="small">Pagina {{ pagina }} di {{ pagine }} · {{ totale }} elementi</span>
    <button type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="pagina >= pagine" @click="vai(pagina + 1)">
      Successiva
    </button>
  </nav>
</template>
