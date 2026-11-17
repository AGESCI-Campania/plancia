<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import { allauth, erroriAllauth } from '@/api/allauth'
import CampoForm from '@/components/CampoForm.vue'

const email = ref('')
const inviata = ref(false)
const errori = ref<Record<string, string[]>>({})

async function invia(): Promise<void> {
  const r = await allauth.richiediResetPassword(email.value)
  if (r.status === 400) errori.value = erroriAllauth(r)
  else inviata.value = true
}
</script>

<template>
  <h1 class="h3 mb-4">Password dimenticata</h1>
  <div v-if="inviata" class="alert theme-success" role="status">
    Se l'indirizzo è registrato, riceverai un'email con il link per scegliere una nuova password.
  </div>
  <form v-else novalidate @submit.prevent="invia">
    <CampoForm v-model="email" etichetta="Email" tipo="email" autocomplete="email" :errori="errori.email" obbligatorio />
    <button type="submit" class="btn btn-solid theme-primary w-100">Invia il link</button>
  </form>
  <p class="mt-6 mb-0"><RouterLink :to="{ name: 'accesso' }">Torna all'accesso</RouterLink></p>
</template>
