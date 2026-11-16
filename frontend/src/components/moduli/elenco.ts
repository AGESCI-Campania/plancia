/** I moduli del Diario di Bordo: numero, titolo, chiave di `stato_moduli`, percorso della pagina. */
export type ChiaveModulo = 'anagrafica' | 'presentazione' | 'impresa_1' | 'impresa_2' | 'missione' | 'relazione_finale'

export interface VoceModulo {
  chiave: ChiaveModulo
  numero: number
  titolo: string
  /** Titolo breve per la navigazione tra i moduli. */
  breve: string
  /** Percorso relativo al diario (`/diari/:id/…`). */
  segmento: string
}

export const MODULI: VoceModulo[] = [
  { chiave: 'anagrafica', numero: 1, titolo: 'Anagrafica', breve: 'Anagrafica', segmento: 'anagrafica' },
  { chiave: 'presentazione', numero: 2, titolo: 'Presentazione della squadriglia', breve: 'Presentazione', segmento: 'presentazione' },
  { chiave: 'impresa_1', numero: 3, titolo: '1ª impresa', breve: '1ª impresa', segmento: 'imprese/1' },
  { chiave: 'impresa_2', numero: 4, titolo: '2ª impresa', breve: '2ª impresa', segmento: 'imprese/2' },
  { chiave: 'missione', numero: 5, titolo: 'Missione', breve: 'Missione', segmento: 'missione' },
  { chiave: 'relazione_finale', numero: 6, titolo: 'Relazione finale del Capo Reparto', breve: 'Relazione finale', segmento: 'relazione-finale' },
]

export function voceModulo(chiave: ChiaveModulo): VoceModulo {
  return MODULI.find((m) => m.chiave === chiave)!
}

export const percorsoModulo = (diarioId: number | string, voce: VoceModulo) => `/diari/${diarioId}/${voce.segmento}`

/** Etichette dei moduli con foto (`Allegato.modulo`). */
export const MODULI_FOTO: { valore: 'impresa_1' | 'impresa_2' | 'missione'; etichetta: string }[] = [
  { valore: 'impresa_1', etichetta: '1ª impresa' },
  { valore: 'impresa_2', etichetta: '2ª impresa' },
  { valore: 'missione', etichetta: 'Missione' },
]
