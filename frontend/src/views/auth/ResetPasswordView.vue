<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { allauth, erroriAllauth } from '@/api/allauth'
import CampoForm from '@/components/CampoForm.vue'
import { useSessioneStore } from '@/stores/sessione'

const props = defineProps<{ chiave: string }>()
const sessione = useSessioneStore()
const router = useRouter()
const valida = ref<boolean | null>(null)
const password = ref('')
const conferma = ref('')
const errori = ref<Record<string, string[]>>({})

onMounted(async () => {
  valida.value = (await allauth.verificaChiaveReset(props.chiave)).status === 200
})

async function salva(): Promise<void> {
  if (password.value !== conferma.value) {
    errori.value = { conferma: ['Le due password non coincidono.'] }
    return
  }
  const r = await sessione.applica(await allauth.resetPassword(props.chiave, password.value))
  if (r.status === 400) errori.value = erroriAllauth(r)
  else await router.replace(sessione.autenticato ? '/' : { name: 'accesso' })
}
</script>

<template>
  <h1 class="h3 mb-4">Nuova password</h1>
  <p v-if="valida === null"><span class="spinner-border spinner-sm" aria-hidden="true" /></p>
  <div v-else-if="!valida" class="alert theme-danger" role="alert">
    Il link non è valido o è scaduto.
    <RouterLink :to="{ name: 'password-dimenticata' }">Richiedine uno nuovo</RouterLink>.
  </div>
  <form v-else novalidate @submit.prevent="salva">
    <div v-for="e in errori.__all__ ?? []" :key="e" class="alert theme-danger">{{ e }}</div>
    <CampoForm v-model="password" etichetta="Nuova password" tipo="password" autocomplete="new-password" :errori="errori.password" obbligatorio />
    <CampoForm v-model="conferma" etichetta="Ripeti la password" tipo="password" autocomplete="new-password" :errori="errori.conferma" obbligatorio />
    <button type="submit" class="btn btn-solid theme-primary w-100">Salva la password</button>
  </form>
</template>
