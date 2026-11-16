<script setup lang="ts">
/**
 * Struttura comune delle pagine dei moduli: intestazione del diario, navigazione tra i
 * moduli, avvisi (sola lettura, conflitto, errori), il form (slot) e la barra di salvataggio.
 */
import { computed } from 'vue'

import BadgeStato from '@/components/BadgeStato.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import { conferma } from '@/composables/conferma'
import type { DiarioDettaglio } from '@/composables/diarioCompilazione'
import type { ModuloDiario } from '@/composables/moduloDiario'

import IndicatoreSalvataggio from './IndicatoreSalvataggio.vue'
import NavigazioneModuli from './NavigazioneModuli.vue'
import { voceModulo, type ChiaveModulo } from './elenco'

const props = withDefaults(
  defineProps<{
    diarioId: number | string
    chiave: ChiaveModulo
    diario: DiarioDettaglio | null
    erroreDiario?: string
    inCorsoDiario?: boolean
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    modulo: ModuloDiario<any>
    solaLettura: boolean
    /** Perché il modulo non è modificabile (mostrato se `solaLettura`). */
    avvisoSolaLettura?: string
    descrizione?: string
  }>(),
  { erroreDiario: '', inCorsoDiario: false, avvisoSolaLettura: '', descrizione: '' },
)
const emit = defineEmits<{ ricaricaDiario: [] }>()

const voce = computed(() => voceModulo(props.chiave))
const m = props.modulo
const inCorso = computed(() => props.inCorsoDiario || m.caricamento.value)
const erroreTotale = computed(() => props.erroreDiario || m.erroreCaricamento.value)

function riprovaCaricamento(): void {
  if (props.erroreDiario) emit('ricaricaDiario')
  if (m.erroreCaricamento.value) void m.carica()
}

async function sovrascrivi(): Promise<void> {
  const ok = await conferma(
    'Le modifiche salvate altrove su questo modulo verranno sostituite da quelle che vedi in questa pagina.',
    { titolo: 'Sovrascrivere il modulo?', testoConferma: 'Sovrascrivi', pericolosa: true },
  )
  if (ok) await m.sovrascrivi()
}

async function ricarica(): Promise<void> {
  const ok = await conferma('Le modifiche fatte in questa pagina e non salvate andranno perse.', {
    titolo: 'Ricaricare il modulo?',
    testoConferma: 'Ricarica',
  })
  if (ok) await m.ricarica()
}
</script>

<template>
  <header class="mb-5">
    <h1 class="h3 mb-1">
      <span class="fg-2 fw-normal">Modulo {{ voce.numero }} —</span> {{ voce.titolo }}
    </h1>
    <p v-if="diario" class="mb-0 d-flex flex-wrap align-items-center gap-2">
      <RouterLink :to="`/diari/${diario.id}`" class="fw-semibold">Squadriglia {{ diario.squadriglia }}</RouterLink>
      <span class="fg-2">{{ diario.reparto }} · {{ diario.gruppo }} · Edizione {{ diario.edizione_anno }}</span>
      <BadgeStato :stato="diario.stato" :etichetta="diario.stato_display" />
      <span class="badge theme-secondary">{{ diario.tipo_display }}</span>
    </p>
    <p v-if="descrizione" class="fg-2 small mt-2 mb-0">{{ descrizione }}</p>
  </header>

  <NavigazioneModuli v-if="diario" :diario="diario" :attivo="chiave" />

  <StatoCaricamento :in-corso="inCorso" :errore="erroreTotale" @riprova="riprovaCaricamento">
    <div v-if="solaLettura && avvisoSolaLettura" class="alert theme-info d-flex gap-2" role="note">
      <IconaBs nome="lock-fill" class="mt-1" />
      <span>{{ avvisoSolaLettura }}</span>
    </div>

    <div v-if="m.conflitto.value" class="alert theme-danger" role="alert">
      <div>
      <p class="fw-semibold mb-2">
        <IconaBs nome="exclamation-octagon-fill" class="me-1" />Questo modulo è stato modificato altrove
      </p>
      <p class="mb-3">
        Qualcuno (o tu da un altro dispositivo) ha salvato il modulo dopo che hai aperto questa pagina.
        Puoi ricaricare la versione salvata, perdendo le modifiche fatte qui, oppure sovrascriverla con
        quella che vedi.
      </p>
      <div class="d-flex flex-wrap gap-2">
        <button type="button" class="btn btn-solid theme-primary btn-sm" @click="ricarica">Ricarica la versione salvata</button>
        <button type="button" class="btn btn-outline theme-danger btn-sm" @click="sovrascrivi">Sovrascrivi con le mie modifiche</button>
      </div>
      </div>
    </div>
    <div v-else-if="m.stato.value === 'errore' && m.errore.value" class="alert theme-warning" role="alert">
      {{ m.errore.value }}
      <span v-if="m.inRipetizione.value"> Le modifiche restano in questa pagina e verranno inviate appena possibile.</span>
    </div>
    <div v-else-if="m.stato.value === 'non_valido'" class="alert theme-danger" role="alert">
      <div>
      {{ m.errore.value }}
      <ul v-if="m.erroriDi('__all__').length" class="mb-0 mt-2">
        <li v-for="e in m.erroriDi('__all__')" :key="e">{{ e }}</li>
      </ul>
      </div>
    </div>

    <form v-if="m.dati.value" novalidate @submit.prevent="m.salvaOra()">
      <slot />
      <IndicatoreSalvataggio
        :stato="m.stato.value"
        :ultimo-salvataggio="m.ultimoSalvataggio.value"
        :in-ripetizione="m.inRipetizione.value"
        :sola-lettura="solaLettura"
        :diario-id="diarioId"
        @salva="m.salvaOra()"
        @ripeti="m.ripeti()"
      />
    </form>
  </StatoCaricamento>
</template>
