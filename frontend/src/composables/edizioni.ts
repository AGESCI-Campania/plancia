/**
 * Logica di presentazione per edizioni, home e valutazioni (senza regole di permesso: quelle
 * restano nel backend, qui solo formati, etichette e trasformazioni dei dati dell'API).
 */
import type { Edizione, EdizioneIn } from '@/api/tipi-edizioni'

/** Data ISO (`AAAA-MM-GG` o data/ora) → `GG/MM/AAAA`; stringa vuota se assente. */
export function formatoData(iso: string | null | undefined): string {
  if (!iso) return ''
  const [a, m, g] = iso.slice(0, 10).split('-')
  return a && m && g ? `${g}/${m}/${a}` : iso
}

/** Data e ora locale leggibile (per `creata_at`, `aggiornata_at`). */
export function formatoDataOra(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })
}

/** "dal … al …" dell'evento, o solo l'inizio. */
export function periodoEvento(e: Pick<Edizione, 'data_evento_inizio' | 'data_evento_fine'>): string {
  if (!e.data_evento_inizio) return ''
  const inizio = formatoData(e.data_evento_inizio)
  return e.data_evento_fine ? `${inizio} – ${formatoData(e.data_evento_fine)}` : inizio
}

/** Stati dell'edizione (FSM bozza → aperta → in valutazione → chiusa) per il form. */
export const STATI_EDIZIONE = [
  { valore: 'bozza', etichetta: 'Bozza' },
  { valore: 'aperta', etichetta: 'Aperta' },
  { valore: 'in_valutazione', etichetta: 'In valutazione' },
  { valore: 'chiusa', etichetta: 'Chiusa' },
] as const

export interface AzioneEdizione {
  azione: 'apri' | 'avvia-valutazione' | 'chiudi'
  etichetta: string
  conferma: string
  tema: string
}

/**
 * Prossimo passo della FSM per lo stato attuale (come i pulsanti della pagina Django);
 * il backend ricontrolla permessi e transizione.
 */
export function azioneSuccessiva(stato: string): AzioneEdizione | null {
  switch (stato) {
    case 'bozza':
      return {
        azione: 'apri',
        etichetta: 'Apri edizione',
        conferma: "Aprire l'edizione? Capi Squadriglia e Capi Reparto potranno compilare i diari.",
        tema: 'success',
      }
    case 'aperta':
      return {
        azione: 'avvia-valutazione',
        etichetta: 'Avvia valutazione',
        conferma: "Avviare la valutazione dell'edizione?",
        tema: 'warning',
      }
    case 'in_valutazione':
      return {
        azione: 'chiudi',
        etichetta: 'Chiudi edizione',
        conferma: "Chiudere l'edizione? L'operazione non si può annullare.",
        tema: 'secondary',
      }
    default:
      return null
  }
}

/** Dati del form edizione (tutti stringhe, come gli `<input>`). */
export interface FormEdizione {
  anno: string
  stato: string
  scadenza_evento: string
  scadenza_assemblea: string
  data_evento_inizio: string
  data_evento_fine: string
  evento_comune: string
  evento_localita: string
}

export function formDaEdizione(e: Edizione | null): FormEdizione {
  return {
    anno: e ? String(e.anno) : String(new Date().getFullYear()),
    stato: e?.stato ?? 'bozza',
    scadenza_evento: e?.scadenza_evento ?? '',
    scadenza_assemblea: e?.scadenza_assemblea ?? '',
    data_evento_inizio: e?.data_evento_inizio ?? '',
    data_evento_fine: e?.data_evento_fine ?? '',
    evento_comune: e?.evento_comune ?? '',
    evento_localita: e?.evento_localita ?? '',
  }
}

/** Corpo per `POST`/`PATCH /edizioni`: date vuote → `null`, testi senza spazi superflui. */
export function corpoEdizione(f: FormEdizione): EdizioneIn {
  const data = (v: string) => (v ? v : null)
  return {
    anno: f.anno.trim() ? Number(f.anno) : null,
    stato: f.stato,
    scadenza_evento: data(f.scadenza_evento),
    scadenza_assemblea: data(f.scadenza_assemblea),
    data_evento_inizio: data(f.data_evento_inizio),
    data_evento_fine: data(f.data_evento_fine),
    evento_comune: f.evento_comune.trim(),
    evento_localita: f.evento_localita.trim(),
  }
}

/** Controlli immediati lato client (il backend ripete la validazione di `EdizioneForm`). */
export function validaEdizione(f: FormEdizione): Record<string, string[]> {
  const errori: Record<string, string[]> = {}
  if (!/^\d{4}$/.test(f.anno.trim())) errori.anno = ["Indica l'anno (quattro cifre)."]
  if (f.data_evento_inizio && f.data_evento_fine && f.data_evento_fine < f.data_evento_inizio) {
    errori.data_evento_fine = ['La data di fine non può precedere quella di inizio.']
  }
  return errori
}

/** Variabili del formato del nome cartella diario (Drive) con il valore d'esempio. */
export const VARIABILI_CARTELLA: Record<string, string> = {
  '{id_univoco}': '00001',
  '{edizione}': '',
  '{nome_gruppo}': 'Salerno1',
  '{nome_zona}': 'Salerno',
  '{nome_reparto}': 'Reparto1',
  '{nome_squadriglia}': 'Aquile',
  '{specialita}': 'Campismo',
}

/**
 * Anteprima del nome della cartella di un diario dal formato (approssimata come nella
 * pagina Django: la sanificazione vera è nel backend).
 */
export function anteprimaCartella(formato: string, anno: number | string): string {
  let nome = formato
  for (const [variabile, esempio] of Object.entries(VARIABILI_CARTELLA)) {
    nome = nome.replaceAll(variabile, variabile === '{edizione}' ? String(anno) : esempio)
  }
  return nome.replace(/[\s/\\]+/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
}

/** Ordinamento della tabella diari: stesso campo → inverte, altro campo → crescente. */
export function ordinamentoSuccessivo(attuale: string, campo: string): string {
  if (attuale === campo) return `-${campo}`
  return campo
}

/** Direzione dell'ordinamento di una colonna (per `aria-sort`). */
export function direzioneOrdinamento(
  attuale: string,
  campo: string,
): 'ascending' | 'descending' | 'none' {
  if (attuale === campo) return 'ascending'
  if (attuale === `-${campo}`) return 'descending'
  return 'none'
}

/** Esiti della valutazione (valori di `EsitoValutazione`). */
export const ESITI = [
  { valore: 'approvata', etichetta: 'Approvata' },
  { valore: 'non_approvata', etichetta: 'Non approvata' },
  { valore: 'maggiori_info', etichetta: 'Maggiori informazioni richieste' },
] as const

/** La Pattuglia GV propone solo Approvata / Non approvata. */
export const ESITI_PROPOSTA = ESITI.filter((e) => e.valore !== 'maggiori_info')

/** Colore del badge per un esito. */
export function coloreEsito(esito: string | null | undefined): string {
  if (esito === 'approvata') return 'success'
  if (esito === 'non_approvata') return 'danger'
  return esito ? 'warning' : 'secondary'
}

/** Messaggio per gli errori di accesso alla valutazione (403/404 dell'API). */
export function messaggioAccessoValutazione(stato: number | null, dettaglio: string): string {
  if (stato === 403) return dettaglio || 'Non puoi vedere la valutazione di questo diario.'
  if (stato === 404) return 'Diario non trovato.'
  return dettaglio
}
