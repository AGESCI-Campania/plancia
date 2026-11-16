<script setup lang="ts">
// Ritorno dal provider social/SSO (callback_url di allauth): controlla la sessione e prosegue.
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSessioneStore } from '@/stores/sessione'

const sessione = useSessioneStore()
const route = useRoute()
const router = useRouter()

onMounted(async () => {
  if (route.query.error) {
    await router.replace({
      name: 'accesso',
      query: { errore: 'Accesso con il provider non riuscito o annullato.' },
    })
    return
  }
  await sessione.carica()
  if (sessione.autenticato) await router.replace('/')
  else if (sessione.passoInSospeso === 'mfa_authenticate') await router.replace({ name: 'accesso-mfa' })
  else
    await router.replace({
      name: 'accesso',
      query: { errore: 'Nessun account di Plancia collegato a questo accesso.' },
    })
})
</script>

<template>
  <p class="text-center"><span class="spinner-border me-2" aria-hidden="true" />Accesso in corso…</p>
</template>
