<script setup lang="ts">
/**
 * Inviti del Capo Reparto: i Capi Squadriglia dei propri diari dell'edizione attiva, con lo
 * stato dell'ultimo invito e il reinvio (nuovo link, il precedente non vale più).
 */
import { onMounted, ref } from 'vue'

import { api, ErroreApi } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import InvitiBadgeInvito from '@/components/inviti/InvitiBadgeInvito.vue'
import type { InvitiCrp } from '@/components/utenti/tipi'
import { conferma } from '@/composables/conferma'
import { useRichiesta } from '@/composables/richiesta'
import { useAvvisiStore } from '@/stores/avvisi'

const avvisi = useAvvisiStore()
const inviti = useRichiesta(() => api.get<InvitiCrp>('/notifiche/inviti/miei'))
const inCorso = ref<number | null>(null)

async function reinvia(invitoId: number, squadriglia: string): Promise<void> {
  const ok = await conferma(
    `Reinviare il link di accesso al Capo Squadriglia di ${squadriglia}? Il link precedente non funzionerà più.`,
    { titolo: 'Reinvia invito', testoConferma: 'Reinvia' },
  )
  if (!ok) return
  inCorso.value = invitoId
  try {
    const r = await api.post<{ detail: string }>(`/notifiche/inviti/${invitoId}/reinvia`)
    avvisi.mostra(r.detail)
    await inviti.esegui()
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Reinvio non riuscito.', 'danger')
  } finally {
    inCorso.value = null
  }
}

onMounted(inviti.esegui)
</script>

<template>
  <h1 class="h3 mb-1">Inviti Capi Squadriglia</h1>
  <p v-if="inviti.dati.value?.edizione" class="fg-2 mb-6">{{ inviti.dati.value.edizione.nome }}</p>

  <StatoCaricamento :in-corso="inviti.inCorso.value && !inviti.dati.value" :errore="inviti.errore.value" @riprova="inviti.esegui">
    <template v-if="inviti.dati.value">
      <div v-if="!inviti.dati.value.edizione" class="alert theme-warning mt-6" role="status">Nessuna edizione attiva.</div>
      <div v-else-if="!inviti.dati.value.righe.length" class="alert theme-info" role="status">
        Non hai squadriglie assegnate in questa edizione.
      </div>
      <template v-else>
        <p class="fg-2 small mb-5">
          Puoi reinviare il link di accesso ai tuoi Capi Squadriglia che non lo hanno ancora ricevuto o
          che lo hanno smarrito. Il link precedente viene invalidato.
        </p>
        <div class="table-card table-responsive">
          <table class="table md:table-stacked align-middle">
            <thead>
              <tr>
                <th scope="col">Squadriglia</th>
                <th scope="col">Capo Squadriglia</th>
                <th scope="col">Email</th>
                <th scope="col">Stato invito</th>
                <th scope="col"><span class="visually-hidden">Azioni</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in inviti.dati.value.righe" :key="r.diario_id">
                <td data-cell="Squadriglia">
                  <span class="fw-semibold">{{ r.squadriglia }}</span><br />
                  <small class="fg-2">{{ r.reparto }}</small>
                </td>
                <td data-cell="Capo Squadriglia">
                  <template v-if="r.csq">{{ r.csq.cognome }} {{ r.csq.nome }}</template>
                  <span v-else class="fg-2">—</span>
                </td>
                <td data-cell="Email" class="text-break">
                  <small v-if="r.csq?.email">{{ r.csq.email }}</small>
                  <small v-else class="text-warning"><IconaBs nome="exclamation-triangle" class="me-1" />Email non disponibile</small>
                </td>
                <td data-cell="Stato invito"><InvitiBadgeInvito :invito="r.ultimo_invito_csq" /></td>
                <td class="text-end">
                  <button
                    v-if="r.reinviabile && r.ultimo_invito_csq"
                    type="button"
                    class="btn btn-outline btn-sm theme-primary"
                    :disabled="inCorso === r.ultimo_invito_csq.id"
                    @click="reinvia(r.ultimo_invito_csq.id, r.squadriglia)"
                  >
                    <IconaBs nome="arrow-clockwise" class="me-1" />Reinvia<span class="visually-hidden"> a {{ r.squadriglia }}</span>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </StatoCaricamento>
</template>
