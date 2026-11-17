<script setup lang="ts">
// Secondo fattore al login: codice dell'app (TOTP), codice di recupero o passkey.
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { allauth, erroriAllauth } from '@/api/allauth'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import { firmaConPasskey, passkeySupportate } from '@/composables/webauthn'
import { vaiDopoAccesso } from '@/composables/destinazione'
import { useSessioneStore } from '@/stores/sessione'

const sessione = useSessioneStore()
const route = useRoute()
const router = useRouter()
const codice = ref('')
const errori = ref<Record<string, string[]>>({})
const tipi = computed(() => sessione.flussi.find((f) => f.id === 'mfa_authenticate')?.types ?? [])

async function esito(r: Awaited<ReturnType<typeof allauth.mfaAutentica>>): Promise<void> {
  await sessione.applica(r)
  if (r.status === 400) errori.value = erroriAllauth(r)
  if (sessione.autenticato)
    await vaiDopoAccesso(router, route.query.next)
}

async function verifica(): Promise<void> {
  errori.value = {}
  await esito(await allauth.mfaAutentica(codice.value.replace(/\s/g, '')))
}

async function conPasskey(): Promise<void> {
  errori.value = {}
  try {
    const opzioni = await allauth.passkeyOpzioniMfa()
    await esito(await allauth.passkeyMfa(await firmaConPasskey(opzioni.data?.request_options)))
  } catch (e) {
    errori.value = { __all__: [e instanceof Error ? e.message : 'Verifica non riuscita.'] }
  }
}
</script>

<template>
  <h1 class="h3 mb-4">Verifica in due passaggi</h1>
  <p>Inserisci il codice dell'app di autenticazione oppure uno dei codici di recupero.</p>
  <div v-for="e in errori.__all__ ?? []" :key="e" class="alert theme-danger" role="alert">{{ e }}</div>
  <form novalidate @submit.prevent="verifica">
    <CampoForm
      v-model="codice"
      etichetta="Codice"
      autocomplete="one-time-code"
      inputmode="numeric"
      :errori="errori.code"
      obbligatorio
    />
    <div class="d-grid gap-3">
      <button type="submit" class="btn btn-solid theme-primary">Verifica</button>
      <button
        v-if="tipi.includes('webauthn') && passkeySupportate()"
        type="button"
        class="btn btn-outline theme-secondary"
        @click="conPasskey"
      >
        <IconaBs nome="fingerprint" class="me-2" />Usa una passkey
      </button>
    </div>
  </form>
</template>
