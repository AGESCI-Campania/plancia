<script setup lang="ts">
/**
 * Modifiche fatte offline che il server non ha accettato all'invio dalla coda: il modulo era
 * stato cambiato altrove (409) o i dati non erano validi (400/422). L'utente le recupera nella
 * pagina (poi le salva o corregge come al solito) oppure le scarta.
 */
import { computed } from 'vue'

import { conferma } from '@/composables/conferma'
import { conChiavi, type ModuloDiario } from '@/composables/moduloDiario'
import { recuperaModificheModulo, scartaVoce, voci } from '@/offline/coda'
import type { VoceCoda } from '@/offline/db'

const props = defineProps<{
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  modulo: ModuloDiario<any>
}>()

const daRisolvere = computed(() =>
  voci.value.filter((v) => v.tipo === 'modulo' && v.percorso === props.modulo.percorso && v.stato !== 'attesa'),
)

const data = (ms: number) => new Date(ms).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })

async function recupera(voce: VoceCoda): Promise<void> {
  const dati = await recuperaModificheModulo(voce)
  // La pagina riparte dalla versione del server con i dati offline: l'autosave li invia
  // (sovrascrivendo) o mostra gli errori da correggere.
  // `modulo` è il composable della pagina: si aggiorna il suo stato, non la prop
  // eslint-disable-next-line vue/no-mutating-props
  props.modulo.dati.value = conChiavi(dati as object)
}

async function scarta(voce: VoceCoda): Promise<void> {
  const ok = await conferma('Le modifiche fatte offline su questo modulo andranno perse.', {
    titolo: 'Scartare le modifiche offline?',
    testoConferma: 'Scarta',
    pericolosa: true,
  })
  if (ok) await scartaVoce(voce)
}
</script>

<template>
  <div v-for="v in daRisolvere" :key="v.id" class="alert theme-warning" role="alert">
    <div>
      <p class="mb-2">
        <strong>Modifiche fatte offline il {{ data(v.creatoAt) }} non salvate.</strong>
        <template v-if="v.stato === 'conflitto'">
          Nel frattempo il modulo è stato modificato da un altro dispositivo o da un'altra persona.
        </template>
        <template v-else>{{ v.errore }}</template>
      </p>
      <div class="d-flex flex-wrap gap-2">
        <button type="button" class="btn btn-solid theme-primary btn-sm" @click="recupera(v)">
          Recupera le mie modifiche
        </button>
        <button type="button" class="btn btn-outline theme-danger btn-sm" @click="scarta(v)">Scartale</button>
      </div>
    </div>
  </div>
</template>
