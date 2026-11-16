/**
 * Dominio "diari" della SPA: tipi delle risposte, filtri dell'elenco sincronizzati con la
 * query string, etichette delle scelte che l'API restituisce come chiavi.
 */
import type { LocationQuery, LocationQueryRaw } from 'vue-router'

import type { components } from '@/api/schema'

type Schemi = components['schemas']

export type DiarioRiga = Schemi['DiarioListaSchema']
export type DiarioDettaglio = Schemi['DiarioDettaglioSchema']
export type FiltriDisponibili = Schemi['FiltriDiariSchema']
export type PermessiDiario = Schemi['PermessiDiarioSchema']
export type StatoPdf = Schemi['PdfStatoSchema']
export type Referente = Schemi['ReferenteSchema']
export type Socio = Schemi['SocioAutocompleteSchema']
export type ValutazioneApi = Schemi['ValutazioneApiSchema']
export type RepartoDiari = Schemi['RepartoDiariSchema']
export type RispostaCambioReferente = Schemi['CambioReferenteRispostaSchema']
export type RispostaCambioCrpReparto = Schemi['CambioCrpRepartoRispostaSchema']
export type StatoDiario = Schemi['DiarioStatoSchema']

// --- Filtri dell'elenco ----------------------------------------------------------------

export const PER_PAGINA = [10, 25, 50, 100] as const
export const PER_PAGINA_PREDEFINITO = 25

export interface FiltriDiari {
  edizione: number | null
  zona: number | null
  gruppo: number | null
  reparto: number | null
  stati: string[]
  tipo: string
  specialita: string
  q: string
  /** Campo di ordinamento dell'API, `-` iniziale per decrescente; '' = ordine del server. */
  ordina: string
  pagina: number
  perPagina: number
}

export function filtriVuoti(): FiltriDiari {
  return {
    edizione: null,
    zona: null,
    gruppo: null,
    reparto: null,
    stati: [],
    tipo: '',
    specialita: '',
    q: '',
    ordina: '',
    pagina: 1,
    perPagina: PER_PAGINA_PREDEFINITO,
  }
}

function primo(valore: LocationQuery[string] | undefined): string {
  const v = Array.isArray(valore) ? valore[0] : valore
  return typeof v === 'string' ? v.trim() : ''
}

function intero(valore: LocationQuery[string] | undefined): number | null {
  const testo = primo(valore)
  if (!/^\d+$/.test(testo)) return null
  const n = Number(testo)
  return n > 0 ? n : null
}

/** Filtri dalla query string (`?edizione=3&stato=inviato,approvato&pagina=2`). */
export function filtriDaQuery(query: LocationQuery): FiltriDiari {
  const perPagina = intero(query.per_pagina)
  return {
    edizione: intero(query.edizione),
    zona: intero(query.zona),
    gruppo: intero(query.gruppo),
    reparto: intero(query.reparto),
    stati: primo(query.stato)
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
    tipo: primo(query.tipo),
    specialita: primo(query.specialita),
    q: primo(query.q),
    ordina: primo(query.ordina),
    pagina: intero(query.pagina) ?? 1,
    perPagina:
      perPagina && (PER_PAGINA as readonly number[]).includes(perPagina)
        ? perPagina
        : PER_PAGINA_PREDEFINITO,
  }
}

/** Query string per i filtri: solo i valori diversi dal predefinito. */
export function queryDaFiltri(f: FiltriDiari): LocationQueryRaw {
  const query: LocationQueryRaw = {}
  if (f.edizione) query.edizione = String(f.edizione)
  if (f.zona) query.zona = String(f.zona)
  if (f.gruppo) query.gruppo = String(f.gruppo)
  if (f.reparto) query.reparto = String(f.reparto)
  if (f.stati.length) query.stato = f.stati.join(',')
  if (f.tipo) query.tipo = f.tipo
  if (f.specialita) query.specialita = f.specialita
  if (f.q.trim()) query.q = f.q.trim()
  if (f.ordina) query.ordina = f.ordina
  if (f.pagina > 1) query.pagina = String(f.pagina)
  if (f.perPagina !== PER_PAGINA_PREDEFINITO) query.per_pagina = String(f.perPagina)
  return query
}

/** Parametri di `GET /diari` per i filtri. */
export function parametriApi(f: FiltriDiari): Record<string, string | number | undefined> {
  return {
    edizione_id: f.edizione ?? undefined,
    zona_id: f.zona ?? undefined,
    gruppo_id: f.gruppo ?? undefined,
    reparto_id: f.reparto ?? undefined,
    stato: f.stati.length ? f.stati.join(',') : undefined,
    tipo: f.tipo || undefined,
    specialita: f.specialita || undefined,
    q: f.q.trim() || undefined,
    ordina: f.ordina || undefined,
    limit: f.perPagina,
    offset: (f.pagina - 1) * f.perPagina,
  }
}

/** Ci sono filtri attivi (esclusi ordinamento e paginazione)? */
export function filtriAttivi(f: FiltriDiari): boolean {
  return Boolean(
    f.edizione ||
    f.zona ||
    f.gruppo ||
    f.reparto ||
    f.stati.length ||
    f.tipo ||
    f.specialita ||
    f.q.trim(),
  )
}

/**
 * Ordinamento al clic su una colonna: crescente, poi decrescente, poi di nuovo crescente
 * (come la tabella web, che alternava i due versi).
 */
export function prossimoOrdinamento(attuale: string, campo: string): string {
  return attuale === campo ? `-${campo}` : campo
}

/** Verso dell'ordinamento di una colonna, per `aria-sort`. */
export function versoOrdinamento(
  attuale: string,
  campo: string,
): 'ascending' | 'descending' | 'none' {
  if (attuale === campo) return 'ascending'
  if (attuale === `-${campo}`) return 'descending'
  return 'none'
}

// --- Presentazione ---------------------------------------------------------------------

export function nomeReferente(r: Referente | null | undefined): string {
  return r ? `${r.cognome} ${r.nome}`.trim() : ''
}

export function formattaData(iso: string | null | undefined): string {
  if (!iso) return ''
  const [a, m, g] = iso.slice(0, 10).split('-')
  return a && m && g ? `${g}/${m}/${a}` : iso
}

export const ETICHETTE_RUOLO_SQ: Record<string, string> = {
  csq: 'Capo Squadriglia',
  vcsq: 'Vice Capo Squadriglia',
  squadrigliere: 'Squadrigliere',
  altro: 'Tutti gli altri',
}

export const ETICHETTE_SENTIERO: Record<string, string> = {
  scoperta: 'Scoperta',
  competenza: 'Competenza',
  responsabilita: 'Responsabilità',
  non_specificato: 'Non specificato',
}

export const ETICHETTE_ESITO_SPECIALITA: Record<string, string> = {
  conquistata: 'Conquistata',
  non_conquistata: 'Non conquistata',
  in_cammino: 'In cammino',
}

export const COLORE_ESITO_SPECIALITA: Record<string, string> = {
  conquistata: 'success',
  non_conquistata: 'danger',
  in_cammino: 'warning',
}

/** Riga dello stato di un modulo nella griglia del dettaglio. */
export interface VoceModulo {
  chiave: string
  numero: number
  etichetta: string
  compilato: boolean
  facoltativo: boolean
  /** Il modulo non si può ancora aprire (relazione prima dell'invio del Capo Squadriglia). */
  nonDisponibile: boolean
  to: string
}

const STATI_PRIMA_RELAZIONE = new Set(['non_iniziato', 'in_compilazione'])

/**
 * Stato dei moduli 1–6 dal dettaglio dell'API (`stato_moduli`): la relazione finale compare
 * solo se l'API la rende visibile (`relazione_finale` non nullo, mai al Capo Squadriglia).
 */
export function vociModuli(d: DiarioDettaglio): VoceModulo[] {
  const s = d.stato_moduli
  const base = `/diari/${d.id}`
  const voci: VoceModulo[] = [
    {
      chiave: 'anagrafica',
      numero: 1,
      etichetta: 'Anagrafica',
      compilato: Boolean(s?.anagrafica),
      facoltativo: false,
      nonDisponibile: false,
      to: `${base}/anagrafica`,
    },
    {
      chiave: 'presentazione',
      numero: 2,
      etichetta: 'Presentazione',
      compilato: Boolean(s?.presentazione),
      facoltativo: false,
      nonDisponibile: false,
      to: `${base}/presentazione`,
    },
    {
      chiave: 'impresa_1',
      numero: 3,
      etichetta: '1ª Impresa',
      compilato: Boolean(s?.impresa_1),
      facoltativo: false,
      nonDisponibile: false,
      to: `${base}/imprese/1`,
    },
    {
      chiave: 'impresa_2',
      numero: 4,
      etichetta: '2ª Impresa',
      compilato: Boolean(s?.impresa_2),
      facoltativo: !s?.impresa_2_obbligatoria,
      nonDisponibile: false,
      to: `${base}/imprese/2`,
    },
    {
      chiave: 'missione',
      numero: 5,
      etichetta: 'Missione',
      compilato: Boolean(s?.missione),
      facoltativo: !s?.missione_obbligatoria,
      nonDisponibile: false,
      to: `${base}/missione`,
    },
  ]
  if (s && s.relazione_finale !== null && s.relazione_finale !== undefined) {
    voci.push({
      chiave: 'relazione_finale',
      numero: 6,
      etichetta: 'Relazione finale del Capo Reparto',
      compilato: s.relazione_finale,
      facoltativo: false,
      nonDisponibile: STATI_PRIMA_RELAZIONE.has(d.stato) && !s.relazione_finale,
      to: `${base}/relazione-finale`,
    })
  }
  return voci
}

/** Stati in cui il diario è già passato allo staff (la valutazione può esistere). */
export const STATI_DOPO_INVIO = new Set([
  'inviato',
  'in_valutazione',
  'in_revisione',
  'approvato',
  'non_approvato',
  'maggiori_info',
])
