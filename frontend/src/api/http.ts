/**
 * Client HTTP della SPA: stessa origine del backend, cookie di sessione e token CSRF di
 * Django. Ogni errore diventa un `ErroreApi` con lo stato e il messaggio da mostrare.
 */

export type ErroriCampo = Record<string, string[]>

export class ErroreApi extends Error {
  constructor(
    readonly stato: number,
    messaggio: string,
    readonly errori: ErroriCampo = {},
    readonly corpo: unknown = null,
  ) {
    super(messaggio)
    this.name = 'ErroreApi'
  }

  /** Rete assente o server irraggiungibile (fetch fallita, nessuna risposta). */
  get offline(): boolean {
    return this.stato === 0
  }
}

export function leggiCookie(nome: string): string {
  const coppia = document.cookie.split('; ').find((c) => c.startsWith(`${nome}=`))
  return coppia ? decodeURIComponent(coppia.slice(nome.length + 1)) : ''
}

const METODI_SICURI = new Set(['GET', 'HEAD', 'OPTIONS'])

export interface OpzioniRichiesta {
  metodo?: string
  corpo?: unknown
  parametri?: Record<string, string | number | boolean | null | undefined>
  intestazioni?: Record<string, string>
  segnale?: AbortSignal
}

function conParametri(url: string, parametri?: OpzioniRichiesta['parametri']): string {
  if (!parametri) return url
  const query = new URLSearchParams()
  for (const [chiave, valore] of Object.entries(parametri)) {
    if (valore !== undefined && valore !== null && valore !== '') query.set(chiave, String(valore))
  }
  const testo = query.toString()
  return testo ? `${url}${url.includes('?') ? '&' : '?'}${testo}` : url
}

function messaggioDa(stato: number, corpo: unknown): string {
  if (corpo && typeof corpo === 'object') {
    const c = corpo as { detail?: unknown; errors?: { message?: string }[] }
    if (typeof c.detail === 'string') return c.detail
    if (Array.isArray(c.detail) && c.detail.length) return 'Dati non validi.'
    if (Array.isArray(c.errors) && c.errors[0]?.message) return c.errors[0].message
  }
  if (stato === 401) return 'Sessione scaduta: accedi di nuovo.'
  if (stato === 403) return 'Non hai i permessi per questa operazione.'
  if (stato === 404) return 'Non trovato.'
  if (stato === 429) return 'Troppe richieste: riprova tra poco.'
  if (stato >= 500) return 'Errore del server: riprova più tardi.'
  return `Errore ${stato}.`
}

/** Richiesta generica; restituisce il corpo JSON (o `null` per 204). */
export async function richiesta<T = unknown>(url: string, opzioni: OpzioniRichiesta = {}): Promise<T> {
  const metodo = (opzioni.metodo ?? 'GET').toUpperCase()
  const intestazioni: Record<string, string> = { Accept: 'application/json', ...opzioni.intestazioni }
  let corpo: BodyInit | undefined
  if (opzioni.corpo instanceof FormData) {
    corpo = opzioni.corpo
  } else if (opzioni.corpo !== undefined) {
    corpo = JSON.stringify(opzioni.corpo)
    intestazioni['Content-Type'] = 'application/json'
  }
  if (!METODI_SICURI.has(metodo)) intestazioni['X-CSRFToken'] = leggiCookie('csrftoken')

  let risposta: Response
  try {
    risposta = await fetch(conParametri(url, opzioni.parametri), {
      method: metodo,
      headers: intestazioni,
      body: corpo,
      credentials: 'same-origin',
      signal: opzioni.segnale,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ErroreApi(0, 'Sei offline o il server non risponde.')
  }

  if (risposta.status === 204) return null as T
  const tipo = risposta.headers.get('Content-Type') ?? ''
  const dati: unknown = tipo.includes('json') ? await risposta.json().catch(() => null) : null
  if (!risposta.ok) {
    const errori = (dati as { errori?: ErroriCampo } | null)?.errori ?? {}
    throw new ErroreApi(risposta.status, messaggioDa(risposta.status, dati), errori, dati)
  }
  return dati as T
}

/** Scaricamento di un file (PDF, Excel…): restituisce il Blob e il nome suggerito. */
export async function scarica(url: string): Promise<{ blob: Blob; nome: string; tipo: string }> {
  const risposta = await fetch(url, { credentials: 'same-origin' }).catch(() => {
    throw new ErroreApi(0, 'Sei offline o il server non risponde.')
  })
  const tipo = risposta.headers.get('Content-Type') ?? ''
  if (!risposta.ok || tipo.includes('json')) {
    const dati: unknown = tipo.includes('json') ? await risposta.json().catch(() => null) : null
    throw new ErroreApi(risposta.ok ? 409 : risposta.status, messaggioDa(risposta.status, dati), {}, dati)
  }
  const disposizione = risposta.headers.get('Content-Disposition') ?? ''
  const nome = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposizione)?.[1] ?? 'file'
  return { blob: await risposta.blob(), nome: decodeURIComponent(nome), tipo }
}

export const api = {
  get: <T>(url: string, parametri?: OpzioniRichiesta['parametri'], segnale?: AbortSignal) =>
    richiesta<T>(`/api/v1${url}`, { parametri, segnale }),
  post: <T>(url: string, corpo?: unknown) => richiesta<T>(`/api/v1${url}`, { metodo: 'POST', corpo }),
  put: <T>(url: string, corpo?: unknown) => richiesta<T>(`/api/v1${url}`, { metodo: 'PUT', corpo }),
  patch: <T>(url: string, corpo?: unknown) => richiesta<T>(`/api/v1${url}`, { metodo: 'PATCH', corpo }),
  delete: <T>(url: string) => richiesta<T>(`/api/v1${url}`, { metodo: 'DELETE' }),
}

/** Lista paginata di django-ninja (`LimitOffsetPagination`). */
export interface Pagina<T> {
  items: T[]
  count: number
}
