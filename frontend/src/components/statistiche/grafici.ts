/**
 * Trasformazioni dei dati grezzi di `GET /statistiche` in righe per i grafici a barre
 * (`StatisticheGraficoBarre.vue`). Nessun calcolo di dominio: solo presentazione.
 */
import type { components } from '@/api/schema'

type Schemi = components['schemas']
export type Statistiche = Schemi['StatisticheSchema']
export type StatZona = Schemi['StatZonaSchema']
export type StatGlobali = Schemi['StatGlobaliSchema']
export type StatTicket = Schemi['StatTicketSchema']

/** Una serie del grafico: colore da un token del tema (verde E/G = primario). */
export interface Serie {
  chiave: string
  etichetta: string
  colore: string
}

export interface RigaGrafico {
  etichetta: string
  valori: Record<string, number>
}

export interface Segmento {
  chiave: string
  etichetta: string
  colore: string
  valore: number
  /** Larghezza in % della barra più lunga del grafico. */
  larghezza: number
}

const COLORE = {
  primario: 'var(--bs-primary-bg)',
  pericolo: 'var(--bs-danger-bg)',
  attenzione: 'var(--bs-warning-bg)',
  neutro: 'var(--bs-secondary-bg)',
  info: 'var(--bs-info-bg)',
}

export const SERIE_ESITI: Serie[] = [
  { chiave: 'approvati', etichetta: 'Approvati', colore: COLORE.primario },
  { chiave: 'non_approvati', etichetta: 'Non approvati', colore: COLORE.pericolo },
  { chiave: 'maggiori_info', etichetta: 'Maggiori informazioni', colore: COLORE.attenzione },
  { chiave: 'altri', etichetta: 'Altri (in corso)', colore: COLORE.neutro },
]

export const SERIE_PUBBLICAZIONE: Serie[] = [
  { chiave: 'approvati', etichetta: 'Approvati', colore: COLORE.primario },
  { chiave: 'non_approvati', etichetta: 'Non approvati', colore: COLORE.pericolo },
  { chiave: 'non_pubblicati', etichetta: 'Esito non pubblicato', colore: COLORE.neutro },
]

export const SERIE_STATO_TICKET: Serie[] = [
  { chiave: 'aperti', etichetta: 'Aperti', colore: COLORE.attenzione },
  { chiave: 'altri', etichetta: 'In lavorazione', colore: COLORE.info },
  { chiave: 'chiusi', etichetta: 'Chiusi', colore: COLORE.primario },
]

export const SERIE_TICKET: Serie[] = [{ chiave: 'count', etichetta: 'Ticket', colore: COLORE.primario }]

const nonNegativo = (n: number) => Math.max(0, n)

export function percentuale(valore: number, totale: number): number {
  return totale > 0 ? Math.round((valore / totale) * 100) : 0
}

export function totaleRiga(riga: RigaGrafico, serie: Serie[]): number {
  return serie.reduce((s, x) => s + (riga.valori[x.chiave] ?? 0), 0)
}

export function massimo(righe: RigaGrafico[], serie: Serie[]): number {
  return righe.reduce((m, r) => Math.max(m, totaleRiga(r, serie)), 0)
}

/** Segmenti di una riga (solo quelli > 0), larghi in proporzione alla riga più lunga. */
export function segmenti(riga: RigaGrafico, serie: Serie[], max: number): Segmento[] {
  return serie
    .map((s) => {
      const valore = riga.valori[s.chiave] ?? 0
      return { ...s, valore, larghezza: max > 0 ? (valore / max) * 100 : 0 }
    })
    .filter((s) => s.valore > 0)
}

/** Esiti per zona: approvati e non approvati (pubblicati), maggiori info, il resto in corso. */
export function righeZone(perZona: StatZona[]): RigaGrafico[] {
  return perZona.map((z) => ({
    etichetta: z.zona.nome,
    valori: {
      approvati: z.approvati,
      non_approvati: z.non_approvati,
      maggiori_info: z.maggiori_info,
      altri: nonNegativo(z.totale - z.approvati - z.non_approvati - z.maggiori_info),
    },
  }))
}

/** Una riga con gli esiti pubblicati dell'edizione sul totale dei diari. */
export function rigaPubblicazione(g: StatGlobali): RigaGrafico {
  return {
    etichetta: 'Tutti i diari',
    valori: {
      approvati: g.approvati,
      non_approvati: g.non_approvati,
      non_pubblicati: nonNegativo(g.totale - g.approvati - g.non_approvati),
    },
  }
}

export function rigaStatoTicket(t: StatTicket): RigaGrafico {
  return {
    etichetta: 'Ticket',
    valori: { aperti: t.aperti, chiusi: t.chiusi, altri: nonNegativo(t.totale - t.aperti - t.chiusi) },
  }
}

export function righeTicket(t: StatTicket): RigaGrafico[] {
  return t.per_categoria.map((c) => ({ etichetta: c.categoria, valori: { count: c.count } }))
}

/** Testo alternativo sintetico di una riga: "Zona A: 3 Approvati, 1 Non approvati (totale 4)". */
export function descriviRiga(riga: RigaGrafico, serie: Serie[]): string {
  const parti = serie
    .filter((s) => (riga.valori[s.chiave] ?? 0) > 0)
    .map((s) => `${riga.valori[s.chiave]} ${s.etichetta.toLowerCase()}`)
  const totale = totaleRiga(riga, serie)
  return `${riga.etichetta}: ${parti.length ? parti.join(', ') : 'nessun dato'} (totale ${totale})`
}
