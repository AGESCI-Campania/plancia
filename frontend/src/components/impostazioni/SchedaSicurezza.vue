<script setup lang="ts">
/** Scheda "Sicurezza": MFA per i ruoli estesi, protezione dai tentativi di accesso (axes), IP bloccati. */
import { onMounted, reactive } from 'vue'

import { api } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import ImpostazioniInterruttore from '@/components/impostazioni/ImpostazioniInterruttore.vue'
import type { AccessoBloccato, Impostazioni } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { dataOra } from '@/composables/impostazioni-editor'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useRichiesta } from '@/composables/richiesta'

const props = defineProps<{ dati: Impostazioni }>()
const emit = defineEmits<{ aggiornate: [Impostazioni] }>()

const s = props.dati.sicurezza
const modulo = reactive({
  mfa_obbligatoria_ruoli_estesi: s.mfa_obbligatoria_ruoli_estesi,
  axes_failure_limit: String(s.axes_failure_limit),
  axes_cooloff_minutes: String(s.axes_cooloff_minutes),
  axes_use_attempt_expiration: s.axes_use_attempt_expiration,
})
const salvataggio = useSalvataggio()

async function salva(): Promise<void> {
  const corpo = {
    ...modulo,
    axes_failure_limit: modulo.axes_failure_limit === '' ? null : Number(modulo.axes_failure_limit),
    axes_cooloff_minutes: modulo.axes_cooloff_minutes === '' ? null : Number(modulo.axes_cooloff_minutes),
  }
  const r = await salvataggio.esegui(() => api.patch<Impostazioni>('/impostazioni/sicurezza', corpo), 'Sicurezza salvata.')
  if (r) emit('aggiornate', r)
}

// --- IP bloccati -----------------------------------------------------------------------------
const accessi = useRichiesta(() => api.get<AccessoBloccato[]>('/impostazioni/axes'))
onMounted(accessi.esegui)
const sblocco = useSalvataggio()

async function sblocca(a: AccessoBloccato): Promise<void> {
  if (await sblocco.esegui(() => api.delete(`/impostazioni/axes/${a.id}`).then(() => true), `IP ${a.ip_address ?? ''} sbloccato.`)) await accessi.esegui()
}
async function sbloccaTutti(): Promise<void> {
  if (!(await conferma('Sbloccare tutti gli IP bloccati?', { testoConferma: 'Sblocca tutti' }))) return
  const r = await sblocco.esegui(() => api.post<{ detail: string }>('/impostazioni/axes/sblocca-tutti'))
  if (r) {
    sblocco.errori.value = {}
    await accessi.esegui()
  }
}
</script>

<template>
  <form class="card mb-6" novalidate aria-labelledby="titolo-sicurezza" @submit.prevent="salva">
    <div class="card-body">
      <h2 id="titolo-sicurezza" class="h5 mb-4"><IconaBs nome="shield-lock" class="me-2" />Sicurezza</h2>
      <h3 class="h6 mb-4">Verifica in due passaggi (MFA)</h3>
      <ImpostazioniInterruttore
        v-model="modulo.mfa_obbligatoria_ruoli_estesi"
        etichetta="MFA obbligatoria per Segreteria e Incaricati EG"
        descrizione="Se disattivato, solo gli Admin sono obbligati ad attivare la MFA. Segreteria e Incaricati EG possono accedere senza."
      />
      <h3 class="h6 border-top pt-5 mb-4">Protezione dai tentativi di accesso</h3>
      <div class="row">
        <div class="md:col-4">
          <CampoForm
            v-model="modulo.axes_failure_limit"
            etichetta="Tentativi prima del blocco"
            tipo="number"
            inputmode="numeric"
            aiuto="Tentativi di accesso errati prima che l'IP venga bloccato."
            :errori="salvataggio.errori.value.axes_failure_limit"
          />
        </div>
        <div class="md:col-4">
          <CampoForm
            v-model="modulo.axes_cooloff_minutes"
            etichetta="Minuti di blocco automatico"
            tipo="number"
            inputmode="numeric"
            aiuto="Dopo quanti minuti l'IP si sblocca da solo. 0 = blocco permanente."
            :errori="salvataggio.errori.value.axes_cooloff_minutes"
          />
        </div>
      </div>
      <ImpostazioniInterruttore
        v-model="modulo.axes_use_attempt_expiration"
        etichetta="Scadenza dei tentativi"
        descrizione="Se attivo, i tentativi falliti scadono dopo il periodo di blocco e non vengono più conteggiati. Consigliato con il blocco automatico."
      />
      <div class="d-flex justify-content-end">
        <button type="submit" class="btn btn-solid theme-primary" :disabled="salvataggio.inCorso.value">
          <IconaBs nome="check-lg" class="me-1" />Salva sicurezza
        </button>
      </div>
    </div>
  </form>

  <section class="card mb-6" aria-labelledby="titolo-axes">
    <div class="card-body">
      <div class="d-flex flex-wrap align-items-center gap-3 mb-4">
        <h2 id="titolo-axes" class="h5 mb-0"><IconaBs nome="shield-exclamation" class="me-2" />IP bloccati</h2>
        <span class="badge" :class="accessi.dati.value?.length ? 'theme-danger' : 'theme-secondary'">
          {{ accessi.dati.value?.length ?? 0 }}
        </span>
        <button
          v-if="accessi.dati.value?.length"
          type="button"
          class="btn btn-outline btn-sm theme-danger ms-auto"
          :disabled="sblocco.inCorso.value"
          @click="sbloccaTutti"
        >
          <IconaBs nome="unlock" class="me-1" />Sblocca tutti
        </button>
      </div>
      <StatoCaricamento
        :in-corso="accessi.inCorso.value"
        :errore="accessi.errore.value"
        :vuoto="!accessi.dati.value?.length"
        messaggio-vuoto="Nessun IP bloccato."
        @riprova="accessi.esegui"
      >
        <div class="table-responsive">
          <table class="table align-middle mb-0">
            <thead>
              <tr>
                <th scope="col">IP</th>
                <th scope="col">Utente tentato</th>
                <th scope="col">Tentativi</th>
                <th scope="col">Ultimo tentativo</th>
                <th scope="col"><span class="visually-hidden">Azioni</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in accessi.dati.value" :key="a.id">
                <td class="fw-semibold">{{ a.ip_address || '—' }}</td>
                <td class="small fg-2 text-break">{{ a.username || '—' }}</td>
                <td><span class="badge theme-warning">{{ a.failures_since_start }}</span></td>
                <td class="small text-nowrap">{{ dataOra(a.attempt_time) }}</td>
                <td class="text-end">
                  <button type="button" class="btn btn-outline btn-sm theme-success" :disabled="sblocco.inCorso.value" @click="sblocca(a)">
                    <IconaBs nome="unlock" class="me-1" />Sblocca
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </StatoCaricamento>
    </div>
  </section>
</template>
