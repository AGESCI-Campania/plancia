/**
 * Client di allauth headless, modalità *browser* (cookie di sessione same-origin + CSRF).
 * Riferimento: https://docs.allauth.org/en/latest/headless/openapi-specification/
 *
 * allauth risponde 200 a sessione autenticata e 401 quando servono altri passi: in quel caso
 * `data.flows` dice quale (es. `mfa_authenticate`). Per questo le funzioni qui non lanciano
 * su 401 ma restituiscono la risposta, che lo store di sessione interpreta.
 */
import { ErroreApi, leggiCookie } from './http'

const BASE = '/_allauth/browser/v1'

export interface Flusso {
  id: string
  provider?: { id: string; name: string }
  is_pending?: boolean
  types?: string[]
}

export interface RispostaAllauth<T = unknown> {
  status: number
  data?: T & { flows?: Flusso[]; user?: { id: number; email: string; display: string } }
  meta?: { is_authenticated?: boolean; session_token?: string; recovery_codes_generated?: boolean }
  errors?: { message: string; code: string; param?: string }[]
}

async function chiama<T = unknown>(
  metodo: string,
  percorso: string,
  corpo?: unknown,
  intestazioni: Record<string, string> = {},
): Promise<RispostaAllauth<T>> {
  let risposta: Response
  try {
    risposta = await fetch(`${BASE}${percorso}`, {
      method: metodo,
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...(corpo !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(metodo !== 'GET' ? { 'X-CSRFToken': leggiCookie('csrftoken') } : {}),
        ...intestazioni,
      },
      body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
    })
  } catch {
    throw new ErroreApi(0, 'Sei offline o il server non risponde.')
  }
  const dati = (await risposta.json().catch(() => ({ status: risposta.status }))) as RispostaAllauth<T>
  dati.status ??= risposta.status
  if (risposta.status >= 500 || risposta.status === 403) {
    throw new ErroreApi(risposta.status, dati.errors?.[0]?.message ?? 'Errore del server.', {}, dati)
  }
  return dati
}

/** Primo messaggio di errore di una risposta 400 (validazione), per campo se indicato. */
export function erroriAllauth(r: RispostaAllauth): Record<string, string[]> {
  const errori: Record<string, string[]> = {}
  for (const e of r.errors ?? []) (errori[e.param ?? '__all__'] ??= []).push(e.message)
  return errori
}

export const allauth = {
  config: () => chiama('GET', '/config'),
  sessione: () => chiama('GET', '/auth/session'),
  esci: () => chiama('DELETE', '/auth/session'),
  /** Email o codice socio: senza "@" si invia come `username` (codice socio). */
  accedi: (identificativo: string, password: string) =>
    chiama(
      'POST',
      '/auth/login',
      identificativo.includes('@')
        ? { email: identificativo.trim(), password }
        : { username: identificativo.trim(), password },
    ),
  mfaAutentica: (code: string) => chiama('POST', '/auth/2fa/authenticate', { code }),
  riautentica: (password: string) => chiama('POST', '/auth/reauthenticate', { password }),
  mfaRiautentica: (code: string) => chiama('POST', '/auth/2fa/reauthenticate', { code }),

  // Passkey (WebAuthn): opzioni dal server, credenziale firmata dal browser, verifica.
  passkeyOpzioniLogin: () => chiama<{ request_options: unknown }>('GET', '/auth/webauthn/login'),
  passkeyLogin: (credential: unknown) => chiama('POST', '/auth/webauthn/login', { credential }),
  passkeyOpzioniMfa: () => chiama<{ request_options: unknown }>('GET', '/auth/webauthn/authenticate'),
  passkeyMfa: (credential: unknown) => chiama('POST', '/auth/webauthn/authenticate', { credential }),

  richiediResetPassword: (email: string) => chiama('POST', '/auth/password/request', { email }),
  verificaChiaveReset: (key: string) =>
    chiama('GET', '/auth/password/reset', undefined, { 'X-Password-Reset-Key': key }),
  resetPassword: (key: string, password: string) =>
    chiama('POST', '/auth/password/reset', { key, password }),
  verificaEmail: (key: string) => chiama('POST', '/auth/email/verify', { key }),
  cambiaPassword: (current_password: string, new_password: string) =>
    chiama('POST', '/account/password/change', { current_password, new_password }),

  emails: () => chiama<{ email: string; primary: boolean; verified: boolean }[]>('GET', '/account/email'),
  autenticatori: () => chiama<{ type: string; created_at: number; last_used_at: number | null; id?: number; name?: string }[]>('GET', '/account/authenticators'),
  totp: () => chiama<{ secret: string; totp_url: string }>('GET', '/account/authenticators/totp'),
  attivaTotp: (code: string) => chiama('POST', '/account/authenticators/totp', { code }),
  disattivaTotp: () => chiama('DELETE', '/account/authenticators/totp'),
  codiciRecupero: () => chiama<{ unused_codes: string[]; total_code_count: number }>('GET', '/account/authenticators/recovery-codes'),
  rigeneraCodiciRecupero: () => chiama('POST', '/account/authenticators/recovery-codes'),
  passkeyOpzioniNuova: () => chiama<{ creation_options: unknown }>('GET', '/account/authenticators/webauthn'),
  aggiungiPasskey: (name: string, credential: unknown) =>
    chiama('POST', '/account/authenticators/webauthn', { name, credential }),
  eliminaPasskey: (authenticators: number[]) =>
    chiama('DELETE', '/account/authenticators/webauthn', { authenticators }),
  // Account social/SSO collegati: `account` è lo uid presso il provider.
  scollegaProvider: (provider: string, account: string) =>
    chiama('DELETE', '/account/providers', { provider, account }),
}

/**
 * Login con un provider social o SSO: allauth vuole un POST di form (non fetch), che porta il
 * browser dal provider e poi torna a `callbackUrl` della SPA.
 */
export function accediConProvider(provider: string, callbackUrl = '/accesso/ritorno'): void {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = `${BASE}/auth/provider/redirect`
  const campi = {
    provider,
    callback_url: callbackUrl,
    process: 'login',
    csrfmiddlewaretoken: leggiCookie('csrftoken'),
  }
  for (const [nome, valore] of Object.entries(campi)) {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = nome
    input.value = valore
    form.appendChild(input)
  }
  document.body.appendChild(form)
  form.submit()
}
