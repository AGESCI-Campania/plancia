<script setup lang="ts">
/**
 * Attivazione dell'account dal link dell'invito (`/invito/<token>`): per i Capi Squadriglia
 * serve il codice socio AGESCI; il backend verifica tutto e apre la sessione.
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api, ErroreApi } from '@/api/http'
import type { components } from '@/api/schema'
import CampoForm from '@/components/CampoForm.vue'
import { useSessioneStore } from '@/stores/sessione'

type DatiInvito = components['schemas']['InvitoPubblicoSchema']

const props = defineProps<{ token: string }>()
const sessione = useSessioneStore()
const router = useRouter()
const invito = ref<DatiInvito | null>(null)
const erroreCarica = ref('')
const codiceSocio = ref('')
const email = ref('')
const errori = ref<Record<string, string[]>>({})
const inCorso = ref(false)

onMounted(async () => {
  try {
    invito.value = await api.get<DatiInvito>(`/notifiche/inviti/${props.token}`)
  } catch (e) {
    erroreCarica.value = e instanceof ErroreApi ? e.message : 'Invito non trovato.'
  }
})

async function attiva(): Promise<void> {
  inCorso.value = true
  errori.value = {}
  try {
    const esito = await api.post<{ detail: string; login: boolean }>(
      `/notifiche/inviti/${props.token}/attiva`,
      { codice_socio: codiceSocio.value, email: email.value },
    )
    if (!esito.login) {
      // Account con credenziali proprie: l'invito non apre la sessione (password e MFA).
      await router.replace({ name: 'accesso', query: { info: esito.detail } })
      return
    }
    await sessione.carica()
    await router.replace('/')
  } catch (e) {
    if (e instanceof ErroreApi) errori.value = { ...e.errori, __all__: [e.message] }
  } finally {
    inCorso.value = false
  }
}
</script>

<template>
  <h1 class="h3 mb-4">Attivazione dell'account</h1>
  <div v-if="erroreCarica" class="alert theme-danger" role="alert">{{ erroreCarica }}</div>
  <p v-else-if="!invito"><span class="spinner-border spinner-sm" aria-hidden="true" /></p>
  <div v-else-if="!invito.attivabile" class="alert theme-danger" role="alert">
    {{ invito.messaggio ?? "L'invito non è più valido." }}
  </div>
  <form v-else novalidate @submit.prevent="attiva">
    <p>
      Invito come <strong>{{ invito.ruolo_target_display }}</strong>
      <template v-if="invito.squadriglia"> della squadriglia <strong>{{ invito.squadriglia }}</strong></template>
      <template v-if="invito.edizione"> ({{ invito.edizione }})</template>.
      <template v-if="invito.richiede_codice_socio">
        Per attivare l'account inserisci il tuo codice socio AGESCI e l'email che userai per accedere.
      </template>
    </p>
    <div v-for="e in errori.__all__ ?? []" :key="e" class="alert theme-danger">{{ e }}</div>
    <CampoForm
      v-if="invito.richiede_codice_socio"
      v-model="codiceSocio"
      etichetta="Codice socio AGESCI"
      inputmode="numeric"
      aiuto="Il numero di 4–8 cifre della tessera AGESCI."
      :errori="errori.codice_socio"
      obbligatorio
    />
    <CampoForm
      v-if="invito.richiede_codice_socio"
      v-model="email"
      etichetta="Email"
      tipo="email"
      autocomplete="email"
      :errori="errori.email"
      obbligatorio
    />
    <button type="submit" class="btn btn-solid theme-primary w-100" :disabled="inCorso">Attiva l'account</button>
  </form>
</template>
