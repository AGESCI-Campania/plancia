<script setup lang="ts">
/**
 * Finestra per cambiare il Capo Squadriglia (ragazzi) o il Capo Reparto (capi) di un diario:
 * `POST /diari/{id}/cambia-csq|cambia-crp`. Le regole (stato, ruolo, socio non provvisorio)
 * le applica il backend; qui solo la scelta del Socio e il messaggio di esito.
 */
import { computed, ref, watch } from 'vue'

import { api, ErroreApi } from '@/api/http'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import DiariSelettoreSocio from '@/components/diari/DiariSelettoreSocio.vue'
import {
  nomeReferente,
  type DiarioDettaglio,
  type RispostaCambioReferente,
  type Socio,
} from '@/components/diari/diari'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ diario: DiarioDettaglio; tipo: 'csq' | 'crp' }>()
const aperta = defineModel<boolean>('aperta', { default: false })
const emit = defineEmits<{ cambiato: [] }>()
const avvisi = useAvvisiStore()

const socio = ref<Socio | null>(null)
const errori = ref<string[]>([])
const inCorso = ref(false)

const ruolo = computed(() => (props.tipo === 'csq' ? 'Capo Squadriglia' : 'Capo Reparto'))
const attuale = computed(() => (props.tipo === 'csq' ? props.diario.csq : props.diario.crp))
const idForm = computed(() => `form-cambia-${props.tipo}`)

watch(aperta, () => {
  socio.value = null
  errori.value = []
})

async function conferma(): Promise<void> {
  errori.value = []
  if (!socio.value) {
    errori.value = [`Scegli il nuovo ${ruolo.value}.`]
    return
  }
  inCorso.value = true
  try {
    const r = await api.post<RispostaCambioReferente>(
      `/diari/${props.diario.id}/cambia-${props.tipo}`,
      {
        socio_id: socio.value.id,
      },
    )
    avvisi.mostra(r.detail)
    aperta.value = false
    emit('cambiato')
  } catch (e) {
    if (e instanceof ErroreApi) {
      errori.value = Object.values(e.errori).flat()
      if (!errori.value.length) errori.value = [e.message]
    } else {
      errori.value = ['Operazione non riuscita.']
    }
  } finally {
    inCorso.value = false
  }
}
</script>

<template>
  <FinestraDialogo v-model:aperta="aperta" :titolo="`Cambia ${ruolo}`">
    <form :id="idForm" novalidate @submit.prevent="conferma">
      <dl class="row small mb-5">
        <dt class="col-5">Squadriglia</dt>
        <dd class="col-7">{{ diario.squadriglia }}</dd>
        <dt class="col-5">Edizione</dt>
        <dd class="col-7">{{ diario.edizione_anno }}</dd>
        <dt class="col-5">Stato</dt>
        <dd class="col-7">{{ diario.stato_display }}</dd>
        <dt class="col-5">{{ ruolo }} attuale</dt>
        <dd class="col-7 mb-0">{{ nomeReferente(attuale) || '—' }}</dd>
      </dl>
      <DiariSelettoreSocio
        v-model="socio"
        :etichetta="`Nuovo ${ruolo}`"
        :categoria="tipo === 'csq' ? 'ragazzo' : 'capo'"
        :aiuto="`Digita almeno 2 caratteri per cercare tra i ${tipo === 'csq' ? 'ragazzi' : 'capi'}.`"
        :errori="errori"
        :escludi="attuale ? [attuale.id] : []"
      />
    </form>
    <template #piede>
      <button type="button" class="btn btn-outline theme-secondary" @click="aperta = false">
        Annulla
      </button>
      <button type="submit" :form="idForm" class="btn btn-solid theme-primary" :disabled="inCorso">
        <span v-if="inCorso" class="spinner-border spinner-sm me-2" aria-hidden="true" />Conferma
        cambio
      </button>
    </template>
  </FinestraDialogo>
</template>
