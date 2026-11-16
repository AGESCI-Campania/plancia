<script setup lang="ts">
/**
 * Stato dell'ultimo invito (Non inviato, Inviato, Attivato, Scaduto) e, per gli inviti in
 * attesa di attivazione, lo stato di consegna dell'email (webhook del provider) con l'errore.
 */
import { computed } from 'vue'

import IconaBs from '@/components/IconaBs.vue'
import { badgeConsegna, dataOra } from '@/components/utenti/formato'
import type { Invito } from '@/components/utenti/tipi'

const props = defineProps<{ invito: Invito | null | undefined }>()

const stato = computed(() => {
  const inv = props.invito
  if (!inv) return null
  if (inv.stato === 'attivato') return { colore: 'success', icona: 'check-circle', testo: 'Attivato' }
  if (inv.stato === 'inviato') return { colore: 'primary', icona: 'envelope', testo: 'Inviato' }
  return { colore: 'secondary', icona: 'clock-history', testo: inv.stato_display }
})
const consegna = computed(() =>
  props.invito?.stato === 'inviato' ? badgeConsegna(props.invito.delivery_status) : null,
)
const titolo = computed(() => {
  const inv = props.invito
  if (!inv) return undefined
  if (inv.stato === 'attivato') return `Attivato il ${dataOra(inv.attivato_at)}`
  return inv.inviato_at ? `Inviato il ${dataOra(inv.inviato_at)}` : undefined
})
</script>

<template>
  <span v-if="!stato" class="small fg-2">Non inviato</span>
  <span v-else class="d-inline-flex flex-column align-items-start gap-1">
    <span class="badge" :class="`theme-${stato.colore}`" :title="titolo">
      <IconaBs :nome="stato.icona" class="me-1" />{{ stato.testo }}
    </span>
    <span
      v-if="consegna"
      class="badge"
      :class="`theme-${consegna.colore}`"
      :title="invito?.delivery_error || invito?.delivery_status_display"
    >
      <IconaBs :nome="consegna.icona" class="me-1" />{{ consegna.testo }}
    </span>
    <span v-if="consegna && invito?.delivery_error" class="small text-danger">{{ invito.delivery_error }}</span>
  </span>
</template>
