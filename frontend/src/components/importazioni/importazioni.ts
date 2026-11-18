/**
 * Logica delle pagine di import: descrizione dei tracciati, controlli lato client prima
 * dell'upload (il backend ripete gli stessi controlli), presentazione delle righe del log.
 */
import type { ErroriCampo } from '@/api/http'
import type { components } from '@/api/schema'

type Schemi = components['schemas']
export type Tracciato = Schemi['TracciatoSchema']
export type LogImportazione = Schemi['LogImportazioneSchema']
export type LogImportazioneDettaglio = Schemi['LogImportazioneDettaglioSchema']
export type RigaImportazione = Schemi['RigaImportazioneSchema']
export type EsitoLancio = Schemi['LancioImportSchema']
export type EsitoRiconcilia = Schemi['RiconciliaOut']
export type EsitoRiprova = Schemi['RiprovaOut']
export type SocioAutocomplete = Schemi['SocioAutocompleteSchema']
export type EdizioneBreve = Pick<Schemi['EdizioneSchema'], 'id' | 'anno' | 'stato' | 'stato_display'>

/** Testi della scheda di un tracciato (come nella pagina Django `imports/log_list.html`). */
export interface DescrizioneTracciato {
  icona: string
  descrizione: string
  /** Etichetta accanto al titolo ("opzionale", "xlsx"). */
  nota?: string
  /** Testo della prima voce del selettore edizione quando l'edizione è facoltativa. */
  edizioneVuota?: string
  /** Accetta un'edizione anche se non obbligatoria. */
  edizioneFacoltativa?: boolean
}

export const DESCRIZIONI_TRACCIATI: Record<string, DescrizioneTracciato> = {
  coca: {
    icona: 'person-badge',
    descrizione:
      "Importa i capi dal tracciato Co.Ca. (export da BuonaStrada). Deve essere eseguito prima " +
      "dell'import squadriglie per consentire l'abbinamento del Capo Reparto.",
  },
  squadriglie: {
    icona: 'flag',
    descrizione:
      "Importa le squadriglie dal CSV dell'evento su BuonaCaccia. Crea i diari e abbina il " +
      'Capo Reparto per email. Le anomalie (Capo Reparto non trovato) si recuperano con ' +
      '"Riprova anomalie" dopo aver completato l\'import capi.',
  },
  ragazzi: {
    icona: 'people',
    nota: 'opzionale',
    descrizione:
      'Importa i ragazzi dal tracciato (export da BuonaStrada). Arricchisce i dati dei Capi ' +
      'Squadriglia tramite codice socio. Se non eseguito, i Capi Squadriglia potranno ' +
      'correggere i propri dati in autonomia dalla piattaforma.',
  },
  risposte_eg: {
    icona: 'journal-check',
    nota: 'xlsx',
    edizioneFacoltativa: true,
    edizioneVuota: 'Edizione più recente aperta',
    descrizione:
      'Importa i diari dal file Excel del Jotform EG (fogli "Risposte EG" e "Risposte staff"). ' +
      "L'elaborazione avviene in background; gli amministratori riceveranno una mail al " +
      'termine con il resoconto completo.',
  },
}

/** Ordine consigliato dei tracciati: Capi → Squadriglie → Ragazzi → Risposte EG, poi il resto. */
const ORDINE = ['coca', 'squadriglie', 'ragazzi', 'risposte_eg']

export function ordinaTracciati(tracciati: Tracciato[]): Tracciato[] {
  const pos = (t: Tracciato) => {
    const i = ORDINE.indexOf(t.chiave)
    return i === -1 ? ORDINE.length : i
  }
  return [...tracciati].sort((a, b) => pos(a) - pos(b))
}

export function descrizione(chiave: string): DescrizioneTracciato {
  return DESCRIZIONI_TRACCIATI[chiave] ?? { icona: 'file-earmark-arrow-up', descrizione: '' }
}

/** Il tracciato chiede un'edizione (obbligatoria o facoltativa). */
export function chiedeEdizione(t: Tracciato): boolean {
  return t.edizione_obbligatoria || Boolean(descrizione(t.chiave).edizioneFacoltativa)
}

export function estensioneValida(nomeFile: string, estensione: string): boolean {
  return nomeFile.toLowerCase().endsWith(estensione.toLowerCase())
}

/**
 * Controlli prima dell'upload, con gli stessi messaggi del backend
 * (`apps.imports.services.lancia_import`). Restituisce gli errori per campo (vuoto se ok).
 */
export function validaLancio(t: Tracciato, file: File | null, edizionePk: string): ErroriCampo {
  const errori: ErroriCampo = {}
  if (!file) errori.file = ["Seleziona un file prima di avviare l'import."]
  else if (!estensioneValida(file.name, t.estensione)) {
    errori.file = [`Il file deve essere in formato ${t.estensione}.`]
  }
  if (t.edizione_obbligatoria && !edizionePk) {
    errori.edizione_pk = ["Seleziona un'edizione per l'import squadriglie iscritte."]
  }
  return errori
}

/** Coppie chiave/valore non vuote dei dati grezzi di una riga (come i template Django). */
export function campiValorizzati(dati: Record<string, unknown>): [string, string][] {
  return Object.entries(dati)
    .filter(([, v]) => v !== null && v !== undefined && String(v).trim() !== '')
    .map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)])
}

/** Tipo di avviso dopo "Riprova anomalie". */
export function tipoAvvisoRiprova(risolte: number, aperte: number): 'success' | 'warning' | 'info' {
  if (risolte) return 'success'
  if (aperte) return 'warning'
  return 'info'
}

/** "scartata" / "scartate" con l'articolo giusto: "1 riga scartata", "3 righe scartate". */
export function righeScartate(n: number): string {
  return n === 1 ? '1 riga scartata' : `${n} righe scartate`
}

export function dataOra(iso: string): string {
  return new Date(iso).toLocaleString('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function etichettaEdizione(e: Pick<EdizioneBreve, 'anno'>): string {
  return `Edizione ${e.anno}`
}
