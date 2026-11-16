/**
 * Uscita da una pagina di modulo: prima si salva ciò che è in attesa; se il salvataggio non
 * riesce (offline, conflitto, campi non validi) si chiede conferma prima di uscire.
 */
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'

import { conferma } from '@/composables/conferma'

interface ModuloSalvabile {
  sporco: { value: boolean }
  salvaOra: () => Promise<boolean>
}

export function useUscitaModulo(modulo: ModuloSalvabile): void {
  const guardia = async (): Promise<boolean> => {
    if (!modulo.sporco.value) return true
    if (await modulo.salvaOra()) return true
    return conferma('Le ultime modifiche a questo modulo non sono state salvate. Uscire comunque?', {
      titolo: 'Modifiche non salvate',
      testoConferma: 'Esci senza salvare',
      pericolosa: true,
    })
  }
  onBeforeRouteLeave(guardia)
  onBeforeRouteUpdate(guardia)
}
