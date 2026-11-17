<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { accediConProvider, allauth, erroriAllauth } from '@/api/allauth'
import { ErroreApi } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import { firmaConPasskey, passkeySupportate } from '@/composables/webauthn'
import { vaiDopoAccesso } from '@/composables/destinazione'
import { useSessioneStore } from '@/stores/sessione'
import { useSitoStore } from '@/stores/sito'

const sessione = useSessioneStore()
const sito = useSitoStore()
const route = useRoute()
const router = useRouter()

const email = ref('')
const password = ref('')
const errori = ref<Record<string, string[]>>({})
const inCorso = ref(false)
const provider = computed(() => sito.sito?.login.provider ?? [])

async function dopoLogin(): Promise<void> {
  if (sessione.autenticato) await vaiDopoAccesso(router, route.query.next)
  else if (sessione.passoInSospeso === 'mfa_authenticate')
    await router.push({ name: 'accesso-mfa', query: route.query })
}

async function accedi(): Promise<void> {
  inCorso.value = true
  errori.value = {}
  try {
    const r = await sessione.applica(await allauth.accedi(email.value, password.value))
    if (r.status === 400) errori.value = erroriAllauth(r)
    await dopoLogin()
  } catch (e) {
    errori.value = { __all__: [e instanceof ErroreApi ? e.message : 'Accesso non riuscito.'] }
  } finally {
    inCorso.value = false
  }
}

async function accediConPasskey(): Promise<void> {
  errori.value = {}
  try {
    const opzioni = await allauth.passkeyOpzioniLogin()
    const credenziale = await firmaConPasskey(opzioni.data?.request_options)
    const r = await sessione.applica(await allauth.passkeyLogin(credenziale))
    if (r.status === 400) errori.value = erroriAllauth(r)
    await dopoLogin()
  } catch (e) {
    errori.value = { __all__: [e instanceof Error ? e.message : 'Accesso con passkey non riuscito.'] }
  }
}
</script>

<template>
  <h1 class="h3 mb-6">Accedi a Plancia</h1>
  <div v-if="route.query.info" class="alert theme-info" role="status">{{ route.query.info }}</div>
  <div v-if="route.query.errore" class="alert theme-danger" role="alert">
    {{ route.query.errore }}
  </div>
  <div v-for="e in errori.__all__ ?? []" :key="e" class="alert theme-danger" role="alert">{{ e }}</div>

  <div v-if="provider.length" class="d-grid gap-3 mb-6">
    <button
      v-for="p in provider"
      :key="p.id"
      type="button"
      class="btn btn-outline theme-primary"
      @click="accediConProvider(p.id)"
    >
      Accedi con {{ p.nome }}
    </button>
  </div>

  <form novalidate @submit.prevent="accedi">
    <CampoForm
      v-model="email"
      etichetta="Email o codice socio"
      autocomplete="username"
      aiuto="I Capi Squadriglia possono usare il codice socio AGESCI."
      :errori="[...(errori.email ?? []), ...(errori.username ?? [])]"
      obbligatorio
    />
    <CampoForm
      v-model="password"
      etichetta="Password"
      tipo="password"
      autocomplete="current-password"
      :errori="errori.password"
      obbligatorio
    />
    <div class="d-grid gap-3">
      <button type="submit" class="btn btn-solid theme-primary" :disabled="inCorso">
        <span v-if="inCorso" class="spinner-border spinner-sm me-2" aria-hidden="true" />Accedi
      </button>
      <button v-if="passkeySupportate()" type="button" class="btn btn-outline theme-secondary" @click="accediConPasskey">
        <IconaBs nome="fingerprint" class="me-2" />Accedi con una passkey
      </button>
    </div>
  </form>
  <p class="mt-6 mb-0">
    <RouterLink :to="{ name: 'password-dimenticata' }">Password dimenticata?</RouterLink>
  </p>
</template>
