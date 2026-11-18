/**
 * Monitoraggio dell'aggiornamento del server (Impostazioni → Aggiornamenti): polling di
 * `GET /aggiornamenti/stato` che regge il riavvio dei container. Durante il riavvio l'API
 * non risponde (rete, 502/504) o risponde 503 di manutenzione: non è un errore, si riprova
 * finché torna; quando la richiesta si chiude (o cambia la versione installata) si ferma.
 */
import { onBeforeUnmount, ref, shallowRef } from 'vue'

import { api, ErroreApi } from '@/api/http'
import type { components } from '@/api/schema'

export type StatoAggiornamento = components['schemas']['StatoAggiornamentoSchema']
export type RichiestaAggiornamento = components['schemas']['RichiestaSchema']

export type Fase = 'in_corso' | 'riavvio' | 'completato' | 'fallito' | 'annullato' | 'errore' | 'inattivo'

export const ESITI_FINALI = new Set(['completato', 'fallito', 'annullato'])

/** Errori che durante un aggiornamento indicano il riavvio del server, non un guasto. */
export function erroreDiRiavvio(e: unknown): boolean {
  if (!(e instanceof ErroreApi)) return false
  return e.offline || e.stato === 502 || e.stato === 503 || e.stato === 504
}

/**
 * Fase da mostrare per una risposta di `/stato`. `versionePartenza` è la versione installata
 * quando è partito il monitoraggio: se cambia, i container nuovi sono su (completato).
 */
export function faseDa(stato: StatoAggiornamento, versionePartenza: string): Fase {
  const esito = stato.richiesta?.stato ?? ''
  if (ESITI_FINALI.has(esito)) return esito as Fase
  if (versionePartenza && stato.installata && stato.installata !== versionePartenza) return 'completato'
  if (stato.in_corso || esito === 'in_attesa' || esito === 'in_corso') return 'in_corso'
  return 'inattivo'
}

/** Righe di log: quelle di `stato.json` (lista) o quelle salvate nello storico (testo). */
export function righeLog(stato: StatoAggiornamento | null): string[] {
  const grezzo = stato?.stato?.log
  if (Array.isArray(grezzo)) return grezzo.map(String)
  const testo = stato?.richiesta?.log ?? ''
  return testo ? testo.split('\n') : []
}

/**
 * Attende che l'nginx serva di nuovo la SPA prima di ricaricarla: a fine aggiornamento il
 * compose ricrea anche l'nginx (immagine nuova) e un ricaricamento in quel momento finirebbe
 * sull'errore di Caddy. Dopo `massimoMs` si ricarica comunque.
 */
export async function attendiSpa(intervalloMs = 2000, massimoMs = 300_000): Promise<void> {
  const fine = Date.now() + massimoMs
  while (Date.now() < fine) {
    try {
      const risposta = await fetch('/index.html', { cache: 'no-store' })
      if (risposta.ok) return
    } catch {
      // nginx non ancora in ascolto: si riprova
    }
    await new Promise((fatto) => setTimeout(fatto, intervalloMs))
  }
}

export interface OpzioniMonitoraggio {
  intervalloMs?: number
  /** Chiamata quando l'aggiornamento è finito (con la fase finale). */
  allaFine?: (fase: Fase, stato: StatoAggiornamento | null) => void
}

export function useMonitoraggioAggiornamento(opzioni: OpzioniMonitoraggio = {}) {
  const intervallo = opzioni.intervalloMs ?? 2000
  const stato = shallowRef<StatoAggiornamento | null>(null)
  const fase = ref<Fase>('inattivo')
  const errore = ref('')
  let partenza = ''
  let timer: ReturnType<typeof setTimeout> | undefined
  let attivo = false

  async function giro(): Promise<void> {
    if (!attivo) return
    try {
      const s = await api.get<StatoAggiornamento>('/aggiornamenti/stato')
      if (!partenza) partenza = s.installata
      stato.value = s
      errore.value = ''
      fase.value = faseDa(s, partenza)
    } catch (e) {
      if (erroreDiRiavvio(e)) {
        fase.value = 'riavvio'
      } else {
        fase.value = 'errore'
        errore.value = e instanceof Error ? e.message : 'Errore imprevisto.'
        attivo = false
        return
      }
    }
    if (fase.value === 'in_corso' || fase.value === 'riavvio') {
      timer = setTimeout(giro, intervallo)
    } else {
      attivo = false
      opzioni.allaFine?.(fase.value, stato.value)
    }
  }

  function avvia(versioneInstallata = ''): void {
    ferma()
    partenza = versioneInstallata
    attivo = true
    fase.value = 'in_corso'
    void giro()
  }

  function ferma(): void {
    attivo = false
    if (timer) clearTimeout(timer)
    timer = undefined
  }

  onBeforeUnmount(ferma)

  return { stato, fase, errore, avvia, ferma }
}
