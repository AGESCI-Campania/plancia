<script setup lang="ts">
/**
 * Avanzamento della generazione massiva dei PDF di un'edizione: polling di
 * `GET /impostazioni/task/{task_id}` ogni 2 s (come la vecchia pagina), pulsante Interrompi.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { api } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import type { EdizioneCachePdf, ProgressoTask } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'

const props = defineProps<{ edizione: EdizioneCachePdf }>()
const emit = defineEmits<{ finito: [] }>()

const progresso = ref<ProgressoTask | null>(null)
const esito = ref<'' | 'completato' | 'errore'>('')
let timer: ReturnType<typeof setTimeout> | undefined
let fermato = false

const percentuale = computed(() => (esito.value === 'completato' ? 100 : (progresso.value?.progresso ?? 0)))
const testo = computed(() => {
  if (esito.value === 'completato') return 'Completato'
  if (esito.value === 'errore') return 'Errore'
  const p = progresso.value
  if (p?.stato === 'PROGRESS') return `${p.completati ?? 0} / ${p.totale ?? 0} diari`
  return 'avvio…'
})

async function giro(): Promise<void> {
  if (fermato || !props.edizione.task_id) return
  try {
    const p = await api.get<ProgressoTask>(`/impostazioni/task/${props.edizione.task_id}`)
    progresso.value = p
    if (p.stato === 'SUCCESS') {
      esito.value = 'completato'
      timer = setTimeout(() => emit('finito'), 1500)
      return
    }
    if (p.stato === 'FAILURE' || p.stato === 'REVOKED') {
      esito.value = 'errore'
      return
    }
    timer = setTimeout(giro, 2000)
  } catch {
    timer = setTimeout(giro, 5000)
  }
}

onMounted(() => {
  timer = setTimeout(giro, 500)
})
onBeforeUnmount(() => {
  fermato = true
  if (timer) clearTimeout(timer)
})

const interruzione = useSalvataggio()
async function interrompi(): Promise<void> {
  if (!(await conferma(`Interrompere la generazione per ${props.edizione.nome}?`, { testoConferma: 'Interrompi', pericolosa: true }))) return
  await interruzione.esegui(
    () => api.post<{ detail: string }>('/impostazioni/cache-pdf/interrompi', { edizione_id: props.edizione.id }),
    'Interruzione richiesta: il task si fermerà dopo il diario in corso.',
  )
}
</script>

<template>
  <div class="mb-4">
    <div class="d-flex flex-wrap align-items-center gap-3 mb-2">
      <span class="small fw-semibold">{{ edizione.nome }}</span>
      <span class="small fg-2 ms-auto" aria-live="polite">{{ testo }}</span>
      <button
        type="button"
        class="btn btn-outline btn-sm theme-danger"
        :disabled="!!esito || interruzione.inCorso.value"
        @click="interrompi"
      >
        <IconaBs nome="stop-fill" class="me-1" />Interrompi
      </button>
    </div>
    <div
      class="progress"
      role="progressbar"
      :aria-label="`Generazione PDF ${edizione.nome}`"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="percentuale"
      style="height: 10px"
    >
      <div
        class="progress-bar"
        :class="{
          'progress-bar-striped progress-bar-animated theme-warning': !esito,
          'theme-success': esito === 'completato',
          'theme-danger': esito === 'errore',
        }"
        :style="{ width: `${percentuale}%` }"
      />
    </div>
  </div>
</template>
