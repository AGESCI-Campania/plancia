/**
 * Database locale della PWA (IndexedDB con Dexie). Contiene dati di minori: per la decisione 5
 * del piano 3.0 non è cifrato, ma è legato all'utente (`meta.utente`) e si cancella al logout
 * e quando entra un altro utente; a sessione scaduta si cancellano le copie delle letture e
 * resta solo ciò che non è ancora stato inviato, finché lo stesso utente rientra.
 */
import Dexie, { type EntityTable } from 'dexie'

/** Copia dell'ultima risposta di una lettura (GET), per mostrare i moduli offline. */
export interface Lettura {
  url: string
  dati: unknown
  salvatoAt: number
}

export type TipoVoceCoda = 'modulo' | 'foto'
/**
 * - `attesa`: da inviare (o in invio);
 * - `conflitto`: il server ha una versione più recente (409): l'utente sceglie dalla pagina;
 * - `non_valido`: il server ha rifiutato i dati (400/422): si correggono dalla pagina;
 * - `rifiutata`: errore definitivo (403, 404, 413…): si mostra e si può solo scartare.
 */
export type StatoVoceCoda = 'attesa' | 'conflitto' | 'non_valido' | 'rifiutata'

export interface VoceCoda {
  id?: number
  tipo: TipoVoceCoda
  diarioId: string
  /** Moduli: percorso relativo a /api/v1 (es. `/diari/12/missione`). */
  percorso: string
  /** Idempotency-Key: la stessa a ogni tentativo di questa voce. */
  chiave: string
  stato: StatoVoceCoda
  creatoAt: number
  tentativi: number
  errore?: string
  /** Moduli: `{version, data}` come per il PUT. */
  corpo?: { version: number; data: unknown }
  /** Foto */
  modulo?: string
  file?: Blob
  nome?: string
}

export interface Meta {
  chiave: string
  valore: unknown
}

export class DatabaseOffline extends Dexie {
  letture!: EntityTable<Lettura, 'url'>
  coda!: EntityTable<VoceCoda, 'id'>
  meta!: EntityTable<Meta, 'chiave'>

  constructor(nome = 'plancia') {
    super(nome)
    this.version(1).stores({
      letture: 'url, salvatoAt',
      coda: '++id, tipo, percorso, diarioId, stato, creatoAt',
      meta: 'chiave',
    })
  }
}

export const db = new DatabaseOffline()
