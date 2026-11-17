/**
 * Impianto comune delle pagine dei moduli: diario e scelte dei campi, modulo con autosave
 * (`useModuloDiario`), sola lettura dai permessi del backend, salvataggio all'uscita.
 */
import { computed, onMounted } from 'vue'

import { voceModulo, type ChiaveModulo } from '@/components/moduli/elenco'
import { useDiarioCompilazione } from '@/composables/diarioCompilazione'
import { useModuloDiario, type OpzioniModuloDiario } from '@/composables/moduloDiario'
import { useUscitaModulo } from '@/composables/uscitaModulo'
import { trasportoOffline } from '@/offline/coda'

const STATI_PRIMA_DELLA_RELAZIONE = new Set(['non_iniziato', 'in_compilazione'])

export function usePaginaModulo<T extends object>(
  diarioId: string,
  chiave: ChiaveModulo,
  opzioni: Pick<OpzioniModuloDiario, 'righeVuote'> = {},
) {
  const compilazione = useDiarioCompilazione(diarioId)
  const { diario } = compilazione
  const relazione = chiave === 'relazione_finale'

  const solaLettura = computed(() => {
    const p = diario.value?.permessi
    if (!p) return true
    return relazione ? !p.puo_modificare_relazione : !p.puo_modificare_moduli
  })

  const modulo = useModuloDiario<T>(diarioId, voceModulo(chiave).segmento, {
    ...opzioni,
    // Offline le scritture vanno in coda sul dispositivo (Fase 5)
    trasporto: trasportoOffline,
    solaLettura,
    dopoSalvataggio: () => {
      const d = diario.value
      // Nome/tipo (anagrafica), completezza o stato cambiati: si aggiorna l'intestazione
      if (chiave === 'anagrafica' || !d?.stato_moduli?.[chiave] || d.stato === 'non_iniziato') void compilazione.aggiorna()
    },
  })
  useUscitaModulo(modulo)

  /** La relazione finale non è mai visibile al Capo Squadriglia (lo dice il backend). */
  const nonVisibile = computed(() => relazione && diario.value?.permessi?.puo_vedere_relazione === false)

  const avvisoSolaLettura = computed(() => {
    const d = diario.value
    if (!d) return ''
    if (relazione && STATI_PRIMA_DELLA_RELAZIONE.has(d.stato))
      return 'La relazione del Capo Reparto è disponibile solo dopo che il Capo Squadriglia ha inviato la propria parte.'
    return `Il modulo è in sola lettura: con il diario nello stato «${d.stato_display}» non puoi modificarlo.`
  })

  async function carica(): Promise<void> {
    if (relazione) {
      // Prima i permessi: al Capo Squadriglia la relazione non si chiede nemmeno
      await compilazione.carica()
      if (!nonVisibile.value && !compilazione.errore.value) await modulo.carica()
      return
    }
    await Promise.all([compilazione.carica(), modulo.carica()])
  }

  onMounted(carica)

  return { ...compilazione, modulo, solaLettura, avvisoSolaLettura, nonVisibile, ricaricaDiario: compilazione.carica }
}
