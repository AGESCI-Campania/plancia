<script setup lang="ts" generic="R extends { _k?: string; id?: number | null }">
/**
 * Righe ripetute di un modulo (membri, posti d'azione, specialità, brevetti): ogni riga è
 * uno slot con i suoi campi, più "Aggiungi" e "Rimuovi". Le righe già salvate chiedono
 * conferma prima di essere tolte (al salvataggio successivo spariscono anche dal server).
 */
import { nextTick, ref } from 'vue'

import IconaBs from '@/components/IconaBs.vue'
import { conferma } from '@/composables/conferma'

const righe = defineModel<R[]>({ required: true })
const props = withDefaults(
  defineProps<{
    /** Crea una riga nuova (con `nuovaRiga()` di moduloDiario). */
    nuova: () => R
    etichettaAggiungi: string
    /** Nome della riga per gli screen reader ("membro", "posto d'azione"…). */
    nomeRiga: string
    solaLettura?: boolean
    messaggioVuoto?: string
  }>(),
  { solaLettura: false, messaggioVuoto: 'Nessuna riga.' },
)

const contenitore = ref<HTMLElement>()

async function aggiungi(): Promise<void> {
  const riga = props.nuova()
  righe.value = [...righe.value, riga]
  await nextTick()
  // Il focus va al primo campo della riga appena aggiunta
  contenitore.value
    ?.querySelector<HTMLElement>(`[data-riga="${riga._k}"] :is(input, select, textarea)`)
    ?.focus()
}

async function rimuovi(riga: R, indice: number): Promise<void> {
  if (riga.id != null) {
    const ok = await conferma(`Rimuovere ${props.nomeRiga} ${indice + 1}?`, {
      titolo: 'Rimuovi riga',
      testoConferma: 'Rimuovi',
      pericolosa: true,
    })
    if (!ok) return
  }
  righe.value = righe.value.filter((r) => r !== riga)
}
</script>

<template>
  <div ref="contenitore">
    <p v-if="!righe.length" class="fg-2 mb-4">{{ messaggioVuoto }}</p>
    <ol v-else class="list-unstyled mb-4 righe-ripetute">
      <li
        v-for="(riga, indice) in righe"
        :key="riga._k ?? indice"
        :data-riga="riga._k"
        class="riga-ripetuta"
        :aria-label="`${nomeRiga} ${indice + 1}`"
      >
        <div class="row g-3 flex-grow-1">
          <slot :riga="riga" :indice="indice" />
        </div>
        <button
          v-if="!solaLettura"
          type="button"
          class="btn btn-text theme-danger btn-icon riga-rimuovi"
          :aria-label="`Rimuovi ${nomeRiga} ${indice + 1}`"
          :title="`Rimuovi ${nomeRiga}`"
          @click="rimuovi(riga, indice)"
        >
          <IconaBs nome="trash" />
        </button>
      </li>
    </ol>
    <button v-if="!solaLettura" type="button" class="btn btn-outline theme-secondary btn-sm" @click="aggiungi">
      <IconaBs nome="plus-lg" class="me-1" />{{ etichettaAggiungi }}
    </button>
  </div>
</template>

<style scoped>
.righe-ripetute {
  display: grid;
  gap: 0.75rem;
}
.riga-ripetuta {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  padding: 0.75rem;
  border: var(--border-width, 1px) solid var(--border-color, #dee2e6);
  border-radius: var(--radius-5, 0.5rem);
}
.riga-rimuovi {
  margin-top: 1.75rem;
  min-width: 2.75rem;
  min-height: 2.75rem;
}
</style>
