<script setup lang="ts">
/**
 * Scheda "Posta elettronica": modalità, mittente, backend standard/massivo, SMTP (o Gmail
 * OAuth), provider transazionale, email di test. I segreti non tornano mai dall'API: un
 * campo password vuoto lascia invariato il valore salvato.
 */
import { computed, reactive, ref } from 'vue'

import { api } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import ImpostazioniInterruttore from '@/components/impostazioni/ImpostazioniInterruttore.vue'
import type { Impostazioni } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useAvvisiStore } from '@/stores/avvisi'
import { useSessioneStore } from '@/stores/sessione'

const props = defineProps<{ dati: Impostazioni }>()
const emit = defineEmits<{ aggiornate: [Impostazioni] }>()
const sessione = useSessioneStore()
const avvisi = useAvvisiStore()

const e = props.dati.email
const modulo = reactive({
  email_mode: e.email_mode,
  from_name: e.from_name,
  from_email: e.from_email,
  email_backend_standard: e.email_backend_standard,
  email_backend_massivo: e.email_backend_massivo,
  smtp_host: e.smtp_host,
  smtp_port: String(e.smtp_port ?? ''),
  smtp_user: e.smtp_user,
  smtp_password: '',
  smtp_use_tls: e.smtp_use_tls,
  email_provider: e.email_provider,
  email_provider_api_key: '',
  email_provider_webhook_secret: '',
})
const gmail = computed(() => props.dati.email.gmail_oauth)
const scelte = computed(() => props.dati.scelte)
const callbackGmail = `${window.location.origin}/impostazioni/gmail-smtp/oauth/callback/`

const salvataggio = useSalvataggio()
const err = computed(() => salvataggio.errori.value)

async function salva(): Promise<void> {
  const corpo: Record<string, unknown> = { ...modulo, smtp_port: modulo.smtp_port === '' ? null : Number(modulo.smtp_port) }
  // segreti vuoti = invariati (non si mandano)
  for (const s of ['smtp_password', 'email_provider_api_key', 'email_provider_webhook_secret']) {
    if (!corpo[s]) delete corpo[s]
  }
  if (gmail.value.attivo) for (const c of ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_use_tls']) delete corpo[c]
  const r = await salvataggio.esegui(() => api.patch<Impostazioni>('/impostazioni/email', corpo), 'Posta elettronica salvata.')
  if (r) {
    modulo.smtp_password = modulo.email_provider_api_key = modulo.email_provider_webhook_secret = ''
    emit('aggiornate', r)
  }
}

// --- Gmail OAuth -----------------------------------------------------------------------------
const oauth = useSalvataggio()
async function collegaGmail(): Promise<void> {
  const r = await oauth.esegui(() => api.post<{ url: string }>('/impostazioni/email/gmail/oauth'))
  if (r?.url) window.location.assign(r.url)
}
async function scollegaGmail(): Promise<void> {
  if (!(await conferma(`Scollegare l'account Gmail ${gmail.value.account}? Si tornerà alla configurazione SMTP manuale.`, { testoConferma: 'Scollega', pericolosa: true }))) return
  const r = await oauth.esegui(() => api.post<Impostazioni>('/impostazioni/email/gmail/disconnetti'), 'Account Gmail scollegato.')
  if (r) emit('aggiornate', r)
}

// --- Email di test ---------------------------------------------------------------------------
const testInCorso = ref<'' | 'smtp' | 'transazionale'>('')
async function inviaTest(backend: 'smtp' | 'transazionale'): Promise<void> {
  testInCorso.value = backend
  try {
    const r = await api.post<{ detail: string }>('/impostazioni/email/test', { backend })
    avvisi.mostra(r.detail, 'success', 8000)
  } catch (errore) {
    avvisi.mostra(errore instanceof Error ? errore.message : 'Invio non riuscito.', 'danger', 10000)
  } finally {
    testInCorso.value = ''
  }
}
</script>

<template>
  <form class="card mb-6" novalidate aria-labelledby="titolo-email" @submit.prevent="salva">
    <div class="card-body">
      <h2 id="titolo-email" class="h5 mb-4"><IconaBs nome="envelope" class="me-2" />Posta elettronica</h2>
      <div class="row">
        <div class="md:col-4 mb-5">
          <label for="email-mode" class="form-label">Modalità invio mail</label>
          <select id="email-mode" v-model="modulo.email_mode" class="form-control" :class="{ 'is-invalid': err.email_mode }">
            <option v-for="s in scelte.email_mode" :key="s.valore" :value="s.valore">{{ s.etichetta }}</option>
          </select>
          <div v-for="m in err.email_mode" :key="m" class="invalid-feedback">{{ m }}</div>
        </div>
        <div class="md:col-4">
          <CampoForm v-model="modulo.from_name" etichetta="Nome mittente" :errori="err.from_name" />
        </div>
        <div class="md:col-4">
          <CampoForm v-model="modulo.from_email" etichetta="Mittente (from)" tipo="email" inputmode="email" :errori="err.from_email" />
        </div>
        <div class="md:col-6 mb-5">
          <label for="email-standard" class="form-label">Backend email standard</label>
          <select id="email-standard" v-model="modulo.email_backend_standard" class="form-control" aria-describedby="email-standard-aiuto">
            <option v-for="s in scelte.email_backend" :key="s.valore" :value="s.valore">{{ s.etichetta }}</option>
          </select>
          <div id="email-standard-aiuto" class="form-text">Email di sistema: reset password, MFA, notifiche singole.</div>
          <div v-for="m in err.email_backend_standard" :key="m" class="invalid-feedback d-block">{{ m }}</div>
        </div>
        <div class="md:col-6 mb-5">
          <label for="email-massivo" class="form-label">Backend invii massivi</label>
          <select id="email-massivo" v-model="modulo.email_backend_massivo" class="form-control" aria-describedby="email-massivo-aiuto">
            <option v-for="s in scelte.email_backend" :key="s.valore" :value="s.valore">{{ s.etichetta }}</option>
          </select>
          <div id="email-massivo-aiuto" class="form-text">Inviti in blocco a Capi Reparto e Capi Squadriglia.</div>
          <div v-for="m in err.email_backend_massivo" :key="m" class="invalid-feedback d-block">{{ m }}</div>
        </div>
      </div>

      <h3 class="h6 border-top pt-5 mb-4">Backend SMTP</h3>
      <div v-if="!gmail.attivo" class="row">
        <div class="md:col-7">
          <CampoForm v-model="modulo.smtp_host" etichetta="SMTP host" :errori="err.smtp_host" />
        </div>
        <div class="md:col-2">
          <CampoForm v-model="modulo.smtp_port" etichetta="Porta" tipo="number" inputmode="numeric" :errori="err.smtp_port" />
        </div>
        <div class="md:col-3 md:pt-6">
          <ImpostazioniInterruttore v-model="modulo.smtp_use_tls" etichetta="Usa TLS" />
        </div>
        <div class="md:col-6">
          <CampoForm v-model="modulo.smtp_user" etichetta="SMTP utente" autocomplete="off" :errori="err.smtp_user" />
        </div>
        <div class="md:col-6">
          <CampoForm
            v-model="modulo.smtp_password"
            etichetta="SMTP password"
            tipo="password"
            autocomplete="new-password"
            :aiuto="e.smtp_password_impostato ? 'Impostata: lascia vuoto per non cambiarla.' : 'Non impostata.'"
            :errori="err.smtp_password"
          />
        </div>
      </div>
      <div v-else class="alert theme-success small" role="status">
        <IconaBs nome="check-circle-fill" class="me-2" />I campi SMTP (host, porta, credenziali) sono
        sostituiti da <strong>Gmail OAuth2</strong>. Scollega l'account per tornare alla configurazione manuale.
      </div>

      <div class="border rounded p-4 mb-5">
        <div class="d-flex flex-wrap align-items-center gap-3">
          <div>
            <strong>Gmail OAuth2 (XOAUTH2)</strong>
            <span v-if="gmail.attivo && gmail.account" class="badge theme-success ms-2">Attivo: {{ gmail.account }}</span>
            <span v-else class="badge theme-secondary ms-2">Non attivo</span>
            <div class="small fg-2">Sostituisce host, utente e password con l'autenticazione OAuth per smtp.gmail.com.</div>
          </div>
          <div class="d-flex gap-2 ms-auto">
            <button type="button" class="btn btn-outline btn-sm theme-primary" :disabled="oauth.inCorso.value" @click="collegaGmail">
              <IconaBs nome="google" class="me-1" />{{ gmail.attivo ? 'Cambia account' : 'Collega Gmail' }}
            </button>
            <button v-if="gmail.attivo" type="button" class="btn btn-outline btn-sm theme-danger" :disabled="oauth.inCorso.value" @click="scollegaGmail">
              Scollega
            </button>
          </div>
        </div>
        <p class="small fg-2 mt-3 mb-0">
          In Google Cloud Console aggiungi <code class="text-break">{{ callbackGmail }}</code> come URI di
          reindirizzamento autorizzato (stesso client OAuth di Drive).
        </p>
      </div>

      <h3 class="h6 border-top pt-5 mb-4">
        Backend provider transazionale <span class="badge theme-info fw-normal ms-1">tracking bounce/errori</span>
      </h3>
      <div class="row">
        <div class="md:col-4 mb-5">
          <label for="email-provider" class="form-label">Provider email</label>
          <select id="email-provider" v-model="modulo.email_provider" class="form-control">
            <option v-for="s in scelte.email_provider" :key="s.valore" :value="s.valore">{{ s.etichetta }}</option>
          </select>
          <div v-for="m in err.email_provider" :key="m" class="invalid-feedback d-block">{{ m }}</div>
        </div>
        <div class="md:col-4">
          <CampoForm
            v-model="modulo.email_provider_api_key"
            etichetta="API key provider"
            tipo="password"
            autocomplete="new-password"
            :aiuto="e.email_provider_api_key_impostato ? 'Impostata: lascia vuoto per non cambiarla.' : 'Non impostata.'"
            :errori="err.email_provider_api_key"
          />
        </div>
        <div class="md:col-4">
          <CampoForm
            v-model="modulo.email_provider_webhook_secret"
            etichetta="Webhook secret"
            tipo="password"
            autocomplete="new-password"
            :aiuto="e.email_provider_webhook_secret_impostato ? 'Impostato: lascia vuoto per non cambiarlo.' : 'Non impostato.'"
            :errori="err.email_provider_webhook_secret"
          />
        </div>
      </div>
      <p class="small fg-2">
        <IconaBs nome="info-circle" class="me-1" />URL del webhook da configurare nel provider:
        <code class="text-break">{{ dati.email.webhook_url }}</code>
      </p>
      <div class="d-flex justify-content-end border-top pt-5">
        <button type="submit" class="btn btn-solid theme-primary" :disabled="salvataggio.inCorso.value">
          <IconaBs nome="check-lg" class="me-1" />Salva posta elettronica
        </button>
      </div>
    </div>
  </form>

  <section class="card mb-6" aria-labelledby="titolo-test-email">
    <div class="card-body">
      <h2 id="titolo-test-email" class="h5">Test invio mail</h2>
      <p class="small fg-2">
        Invia una mail di test a <strong>{{ sessione.me?.email }}</strong> con il backend configurato
        (ignora la modalità simulata). Salva prima le modifiche.
      </p>
      <div class="d-flex flex-wrap gap-3">
        <button type="button" class="btn btn-outline theme-info" :disabled="!!testInCorso" @click="inviaTest('smtp')">
          <span v-if="testInCorso === 'smtp'" class="spinner-border spinner-border-sm me-1" aria-hidden="true" />
          <IconaBs v-else nome="send" class="me-1" />Test SMTP
        </button>
        <button type="button" class="btn btn-outline theme-secondary" :disabled="!!testInCorso" @click="inviaTest('transazionale')">
          <span v-if="testInCorso === 'transazionale'" class="spinner-border spinner-border-sm me-1" aria-hidden="true" />
          <IconaBs v-else nome="send" class="me-1" />Test provider transazionale
        </button>
      </div>
    </div>
  </section>
</template>
