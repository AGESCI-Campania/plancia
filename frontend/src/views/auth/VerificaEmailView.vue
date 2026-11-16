<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { allauth } from '@/api/allauth'
import { useSessioneStore } from '@/stores/sessione'

const props = defineProps<{ chiave: string }>()
const sessione = useSessioneStore()
const esito = ref<'attesa' | 'ok' | 'errore'>('attesa')

onMounted(async () => {
  const r = await sessione.applica(await allauth.verificaEmail(props.chiave))
  esito.value = r.status === 200 || r.status === 401 ? 'ok' : 'errore'
})
</script>

<template>
  <h1 class="h3 mb-4">Conferma dell'email</h1>
  <p v-if="esito === 'attesa'"><span class="spinner-border spinner-sm" aria-hidden="true" /></p>
  <div v-else-if="esito === 'ok'" class="alert theme-success">
    Indirizzo confermato. <RouterLink to="/">Vai a Plancia</RouterLink>
  </div>
  <div v-else class="alert theme-danger">Il link di conferma non è valido o è scaduto.</div>
</template>
