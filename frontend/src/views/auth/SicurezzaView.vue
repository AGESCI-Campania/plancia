<script setup lang="ts">
/**
 * Password e sicurezza: cambio password, app di autenticazione (TOTP), passkey e codici di
 * recupero, tutto via allauth headless. Le operazioni sensibili chiedono la riautenticazione.
 */
import QRCode from 'qrcode'
import { computed, onMounted, ref } from 'vue'

import { allauth, erroriAllauth } from '@/api/allauth'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import { conRiautenticazioneAllauth } from '@/composables/riautenticazione'
import { creaPasskey, passkeySupportate } from '@/composables/webauthn'
import { useSessioneStore } from '@/stores/sessione'

interface Autenticatore {
  type: string
  id?: number
  name?: string
  created_at: number
  last_used_at: number | null
}

const sessione = useSessioneStore()
const autenticatori = ref<Autenticatore[]>([])
const messaggio = ref('')
const errori = ref<Record<string, string[]>>({})

const totpAttivo = computed(() => autenticatori.value.some((a) => a.type === 'totp'))
const passkey = computed(() => autenticatori.value.filter((a) => a.type === 'webauthn'))

async function caricaAutenticatori(): Promise<void> {
  autenticatori.value = ((await allauth.autenticatori()).data ?? []) as Autenticatore[]
}
onMounted(caricaAutenticatori)

const data = (secondi: number | null) =>
  secondi ? new Date(secondi * 1000).toLocaleDateString('it-IT') : 'mai'

// --- Password -------------------------------------------------------------------------
const passwordAttuale = ref('')
const passwordNuova = ref('')
async function cambiaPassword(): Promise<void> {
  errori.value = {}
  const r = await allauth.cambiaPassword(passwordAttuale.value, passwordNuova.value)
  if (r.status === 400) errori.value = erroriAllauth(r)
  else {
    messaggio.value = 'Password cambiata.'
    passwordAttuale.value = passwordNuova.value = ''
  }
}

// --- App di autenticazione (TOTP) ------------------------------------------------------
const configurazioneTotp = ref<{ segreto: string; qr: string } | null>(null)
const codiceTotp = ref('')
async function iniziaTotp(): Promise<void> {
  const r = await conRiautenticazioneAllauth(() => allauth.totp())
  // allauth risponde 404 con il segreto da configurare quando il TOTP non è ancora attivo
  const meta = (r as { meta?: { secret?: string; totp_url?: string } }).meta
  if (meta?.secret && meta.totp_url) {
    configurazioneTotp.value = { segreto: meta.secret, qr: await QRCode.toDataURL(meta.totp_url) }
  }
}
async function confermaTotp(): Promise<void> {
  errori.value = {}
  const r = await conRiautenticazioneAllauth(() => allauth.attivaTotp(codiceTotp.value))
  if (r.status === 400) errori.value = erroriAllauth(r)
  else {
    configurazioneTotp.value = null
    codiceTotp.value = ''
    messaggio.value = 'App di autenticazione attivata. Salva i codici di recupero.'
    await Promise.all([caricaAutenticatori(), sessione.caricaProfilo()])
    await mostraCodici()
  }
}
async function disattivaTotp(): Promise<void> {
  await conRiautenticazioneAllauth(() => allauth.disattivaTotp())
  await Promise.all([caricaAutenticatori(), sessione.caricaProfilo()])
}

// --- Passkey -------------------------------------------------------------------------------
const nomePasskey = ref('')
async function aggiungiPasskey(): Promise<void> {
  errori.value = {}
  try {
    const opzioni = await conRiautenticazioneAllauth(() => allauth.passkeyOpzioniNuova())
    const credenziale = await creaPasskey(opzioni.data?.creation_options)
    const r = await allauth.aggiungiPasskey(nomePasskey.value || 'Passkey', credenziale)
    if (r.status === 400) errori.value = erroriAllauth(r)
    nomePasskey.value = ''
    await caricaAutenticatori()
  } catch (e) {
    errori.value = { passkey: [e instanceof Error ? e.message : 'Passkey non creata.'] }
  }
}
async function eliminaPasskey(id: number | undefined): Promise<void> {
  if (id === undefined) return
  await conRiautenticazioneAllauth(() => allauth.eliminaPasskey([id]))
  await caricaAutenticatori()
}

// --- Codici di recupero --------------------------------------------------------------------
const codici = ref<string[]>([])
async function mostraCodici(): Promise<void> {
  const r = await conRiautenticazioneAllauth(() => allauth.codiciRecupero())
  codici.value = r.data?.unused_codes ?? []
}
async function rigeneraCodici(): Promise<void> {
  await conRiautenticazioneAllauth(() => allauth.rigeneraCodiciRecupero())
  await mostraCodici()
}
</script>

<template>
  <h1 class="h3 mb-6">Password e sicurezza</h1>
  <div v-if="messaggio" class="alert theme-success" role="status">{{ messaggio }}</div>
  <div v-if="sessione.me?.mfa_da_configurare && !totpAttivo && !passkey.length" class="alert theme-warning" role="alert">
    Con il tuo ruolo la verifica in due passaggi è obbligatoria: configura l'app di autenticazione
    o una passkey per continuare a usare Plancia.
  </div>

  <section class="card mb-6">
    <div class="card-body">
      <h2 class="h5">Cambia password</h2>
      <form novalidate @submit.prevent="cambiaPassword">
        <CampoForm v-model="passwordAttuale" etichetta="Password attuale" tipo="password" autocomplete="current-password" :errori="errori.current_password" />
        <CampoForm v-model="passwordNuova" etichetta="Nuova password" tipo="password" autocomplete="new-password" :errori="errori.new_password" />
        <button type="submit" class="btn btn-solid theme-primary">Cambia password</button>
      </form>
    </div>
  </section>

  <section class="card mb-6">
    <div class="card-body">
      <h2 class="h5">App di autenticazione</h2>
      <template v-if="totpAttivo">
        <p><IconaBs nome="check-circle-fill" class="text-success me-2" />Attiva.</p>
        <button type="button" class="btn btn-outline theme-danger" @click="disattivaTotp">Disattiva</button>
      </template>
      <template v-else-if="configurazioneTotp">
        <p>Inquadra il codice con l'app (es. Google Authenticator, Authy) e inserisci il codice che mostra.</p>
        <img :src="configurazioneTotp.qr" alt="Codice QR per l'app di autenticazione" width="200" height="200" />
        <p class="small">Oppure inserisci a mano: <code>{{ configurazioneTotp.segreto }}</code></p>
        <form novalidate @submit.prevent="confermaTotp">
          <CampoForm v-model="codiceTotp" etichetta="Codice" inputmode="numeric" autocomplete="one-time-code" :errori="errori.code" />
          <button type="submit" class="btn btn-solid theme-primary">Attiva</button>
        </form>
      </template>
      <button v-else type="button" class="btn btn-solid theme-primary" @click="iniziaTotp">Configura</button>
    </div>
  </section>

  <section class="card mb-6">
    <div class="card-body">
      <h2 class="h5">Passkey</h2>
      <ul v-if="passkey.length" class="list-group mb-4">
        <li v-for="p in passkey" :key="p.id" class="list-group-item d-flex align-items-center">
          <span><IconaBs nome="fingerprint" class="me-2" />{{ p.name || 'Passkey' }}
            <small class="fg-2 ms-2">usata: {{ data(p.last_used_at) }}</small></span>
          <button type="button" class="btn btn-text btn-sm theme-danger ms-auto" @click="eliminaPasskey(p.id)">Elimina</button>
        </li>
      </ul>
      <form v-if="passkeySupportate()" class="d-flex gap-3 align-items-end" novalidate @submit.prevent="aggiungiPasskey">
        <div class="flex-grow-1">
          <CampoForm v-model="nomePasskey" etichetta="Nome (es. iPhone)" :errori="errori.passkey" />
        </div>
        <button type="submit" class="btn btn-outline theme-primary mb-5">Aggiungi passkey</button>
      </form>
      <p v-else class="fg-2 mb-0">Questo browser non supporta le passkey.</p>
    </div>
  </section>

  <section v-if="totpAttivo" class="card">
    <div class="card-body">
      <h2 class="h5">Codici di recupero</h2>
      <p>Servono per accedere se perdi il telefono. Conservali in un posto sicuro.</p>
      <ul v-if="codici.length" class="list-unstyled font-monospace">
        <li v-for="c in codici" :key="c">{{ c }}</li>
      </ul>
      <div class="d-flex gap-3">
        <button type="button" class="btn btn-outline theme-secondary" @click="mostraCodici">Mostra</button>
        <button type="button" class="btn btn-outline theme-warning" @click="rigeneraCodici">Rigenera</button>
      </div>
    </div>
  </section>
</template>
