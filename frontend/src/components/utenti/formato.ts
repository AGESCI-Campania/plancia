/**
 * Formattazione per le pagine di utenti, profilo, inviti e helpdesk: date in italiano,
 * colori dei badge (solo presentazione), descrizione breve dei browser delle sessioni.
 */

const FORMATO_DATA = new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' })
const FORMATO_DATA_ORA = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function valida(valore: string | null | undefined): Date | null {
  if (!valore) return null
  const d = new Date(valore)
  return Number.isNaN(d.getTime()) ? null : d
}

/** "16/11/2026" (o "—" se manca). */
export function data(valore: string | null | undefined): string {
  const d = valida(valore)
  return d ? FORMATO_DATA.format(d) : '—'
}

/** "16/11/2026, 14:05" (o "—" se manca). */
export function dataOra(valore: string | null | undefined): string {
  const d = valida(valore)
  return d ? FORMATO_DATA_ORA.format(d) : '—'
}

/** Colore del badge di un ruolo (come `ruolo_badge_class` della 2.x). */
export function coloreRuolo(ruolo: string): string {
  return (
    {
      admin: 'danger',
      segreteria: 'primary',
      incaricato_eg: 'info',
      csq: 'success',
      crp: 'warning',
      pgv: 'info',
    }[ruolo] ?? 'secondary'
  )
}

/** Colore del badge dell'esito di un accesso. */
export function coloreEsitoAccesso(esito: string): string {
  if (esito === 'login') return 'success'
  if (esito === 'logout') return 'secondary'
  return 'danger'
}

/** Colore del badge dello stato di un ticket (come i template della 2.x). */
export function coloreStatoTicket(stato: string): string {
  return { aperto: 'danger', in_lavorazione: 'warning', chiuso: 'success' }[stato] ?? 'secondary'
}

export interface BadgeConsegna {
  colore: string
  icona: string
  testo: string
}

/**
 * Stato di consegna di un invito ancora da attivare (webhook del provider): `null` se non
 * c'è nulla da segnalare (in attesa o solo passato al provider).
 */
export function badgeConsegna(stato: string): BadgeConsegna | null {
  switch (stato) {
    case 'bounce':
      return { colore: 'danger', icona: 'x-circle', testo: 'Non recapitato' }
    case 'spam':
      return { colore: 'warning', icona: 'shield-exclamation', testo: 'Segnalato come spam' }
    case 'fallito':
      return { colore: 'danger', icona: 'exclamation-triangle', testo: 'Errore di invio' }
    case 'consegnato':
      return { colore: 'success', icona: 'check2', testo: 'Consegnato' }
    default:
      return null
  }
}

/** "Safari su iPhone", "Chrome su Windows"… a partire dallo user agent (indicativo). */
export function descriviBrowser(userAgent: string): string {
  const ua = userAgent || ''
  if (!ua) return 'Dispositivo sconosciuto'
  const browser = /Edg\//.test(ua)
    ? 'Edge'
    : /Firefox\//.test(ua)
      ? 'Firefox'
      : /(Chrome|CriOS)\//.test(ua)
        ? 'Chrome'
        : /Safari\//.test(ua)
          ? 'Safari'
          : 'Browser'
  const sistema = /iPhone/.test(ua)
    ? 'iPhone'
    : /iPad/.test(ua)
      ? 'iPad'
      : /Android/.test(ua)
        ? 'Android'
        : /Mac OS X|Macintosh/.test(ua)
          ? 'Mac'
          : /Windows/.test(ua)
            ? 'Windows'
            : /Linux/.test(ua)
              ? 'Linux'
              : ''
  return sistema ? `${browser} su ${sistema}` : browser
}

/**
 * Messaggio generale di un errore dell'API per un form: errori non di campo (`__all__`) e
 * quelli dei campi che il form non mostra; altrimenti il messaggio dell'errore, se nessun
 * campo mostrato ha errori.
 */
export function messaggioErrore(
  messaggio: string,
  errori: Record<string, string[]>,
  campiMostrati: readonly string[] = [],
): string {
  const altri = Object.entries(errori)
    .filter(([campo]) => !campiMostrati.includes(campo))
    .flatMap(([, testi]) => testi)
  if (altri.length) return altri.join(' ')
  return campiMostrati.some((c) => errori[c]?.length) ? '' : messaggio
}

/** Valore di un parametro di query come stringa (primo valore se ripetuto). */
export function testoQuery(valore: unknown): string {
  if (Array.isArray(valore)) return typeof valore[0] === 'string' ? valore[0] : ''
  return typeof valore === 'string' ? valore : ''
}

/** Offset di paginazione da un parametro di query (intero ≥ 0). */
export function offsetQuery(valore: unknown): number {
  const n = Number.parseInt(testoQuery(valore), 10)
  return Number.isFinite(n) && n > 0 ? n : 0
}
