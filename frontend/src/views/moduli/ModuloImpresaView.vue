<script setup lang="ts">
// Moduli 3–4: un'istanza del form per ogni impresa (passando dalla 1ª alla 2ª si salva e si ricrea).
import { computed } from 'vue'

import FormImpresa from '@/components/moduli/FormImpresa.vue'

const props = defineProps<{ id: string; numero: string }>()
const n = computed(() => (props.numero === '2' ? 2 : 1))
</script>

<template>
  <FormImpresa :id="id" :key="`${id}-${n}`" :numero="n" />
</template>
