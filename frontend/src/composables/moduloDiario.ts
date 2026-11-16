/**
 * Compilazione di un modulo del Diario di Bordo (1–6): lettura, salvataggio versionato
 * (`{version, data}`, 409 sui conflitti) con `Idempotency-Key`, autosave con debounce e
 * salvataggio all'uscita, errori per campo (400 `{error: "validation", errors}` dei moduli,
 * 422 `{detail, errori}`), ripetizione automatica quando la rete o il server non rispondono.
 *
 * **Tutte le scritture passano da `salva()`**, che consegna ogni invio al `trasporto`:
 * in Fase 5 il trasporto di rete (`trasportoRete`) si sostituisce con la coda offline
 * (outbox Dexie, stessa `ScritturaModulo` con la sua chiave) senza cambiare le pagine.
 *
 * Righe ripetute (membri, posti d'azione, specialità, brevetti…): ogni oggetto negli array
 * di primo livello riceve una chiave locale `_k` (mai inviata: i campi che iniziano con `_`
 * non vanno al server) che serve da `key` nei `v-for`, per riportare sulla riga giusta gli
 * `id` assegnati dal server alle righe nuove e gli errori per riga.
 */
import { getCurrentScope, onScopeDispose, ref, toValue, watch, type MaybeRefOrGetter, type Ref } from 'vue'

import { ErroreApi, richiesta } from '@/api/http'

// ---------------------------------------------------------------------------
// Tipi
// ---------------------------------------------------------------------------

/** Risposta di lettura e scrittura dei moduli: `version` 0 = modulo mai salvato. */
export interface ModuloVersionato<T = unknown> {
  version: number | null
  data: T
}

/** Una scrittura, così come la riceve il trasporto (rete oggi, coda offline in Fase 5). */
export interface ScritturaModulo {
  /** Percorso relativo a `/api/v1` (es. `/diari/12/imprese/1`). */
  percorso: string
  corpo: { version: number; data: unknown }
  /** Uguale per i tentativi ripetuti dello stesso salvataggio, nuova per ogni salvataggio diverso. */
  chiave: string
}

export interface TrasportoModulo {
  leggi: (percorso: string) => Promise<ModuloVersionato>
  scrivi: (scrittura: ScritturaModulo) => Promise<ModuloVersionato>
}

/** Trasporto predefinito: GET/PUT diretti all'API con l'header `Idempotency-Key`. */
export const trasportoRete: TrasportoModulo = {
  leggi: (percorso) => richiesta<ModuloVersionato>(`/api/v1${percorso}`),
  scrivi: (s) =>
    richiesta<ModuloVersionato>(`/api/v1${s.percorso}`, {
      metodo: 'PUT',
      corpo: s.corpo,
      intestazioni: { 'Idempotency-Key': s.chiave },
    }),
}

/**
 * - `salvato`: i dati sul server coincidono con quelli della pagina;
 * - `da_salvare`: modifiche in attesa del debounce;
 * - `salvataggio`: invio in corso;
 * - `errore`: invio non riuscito (`errore` ha il messaggio; se `inRipetizione`, riprova da solo);
 * - `non_valido`: il server ha rifiutato dei campi (`errori`);
 * - `conflitto`: il modulo è stato modificato altrove (`conflitto.versioneServer`).
 */
export type StatoSalvataggio = 'salvato' | 'da_salvare' | 'salvataggio' | 'errore' | 'non_valido' | 'conflitto'

/** Errori per campo: messaggi, o (per le liste) errori per riga indicizzati per chiave `_k`. */
export type ErroriModulo = Record<string, string[] | Record<string, Record<string, string[]>>>

type Oggetto = Record<string, unknown>
type Riga = Oggetto & { _k?: string; id?: number | null }

export interface OpzioniModuloDiario {
  /** Attesa dopo l'ultima modifica prima dell'autosave (ms). */
  ritardoMs?: number
  /** `false` = solo salvataggio esplicito (`salva()`, all'uscita). */
  autosave?: boolean
  /** Il modulo non è modificabile: nessuna scrittura. */
  solaLettura?: MaybeRefOrGetter<boolean>
  /** Per lista: quando una riga senza `id` è vuota e non va inviata (es. riga appena aggiunta). */
  righeVuote?: Record<string, (riga: Oggetto) => boolean>
  trasporto?: TrasportoModulo
  /** Attese tra le ripetizioni automatiche dopo un errore di rete/server (ms; l'ultima si ripete). */
  ritentaMs?: number[]
  generaChiave?: () => string
  /** Dopo ogni salvataggio riuscito (es. per aggiornare lo stato del diario nell'intestazione). */
  dopoSalvataggio?: (risposta: ModuloVersionato) => void
  /** Ascolta `visibilitychange`, `pagehide`, `beforeunload`, `online` (default sì). */
  eventiFinestra?: boolean
}

// ---------------------------------------------------------------------------
// Funzioni pure (esportate per i test e per le pagine)
// ---------------------------------------------------------------------------

let contatoreRighe = 0

/** Nuova riga di una lista, con la chiave locale `_k`. */
export function nuovaRiga<R extends Oggetto>(campi: R): R & { _k: string } {
  contatoreRighe += 1
  return { ...campi, _k: `r${contatoreRighe}` }
}

const eOggetto = (v: unknown): v is Oggetto => typeof v === 'object' && v !== null && !Array.isArray(v)

/** Copia dei dati con `_k` su ogni riga degli array di primo livello. */
export function conChiavi<T>(dati: T): T {
  if (!eOggetto(dati)) return dati
  const copia: Oggetto = {}
  for (const [campo, valore] of Object.entries(dati)) {
    copia[campo] = Array.isArray(valore)
      ? valore.map((r) => (eOggetto(r) ? (r._k ? { ...r } : nuovaRiga(r)) : r))
      : valore
  }
  return copia as T
}

export interface DatiPreparati {
  /** Corpo da inviare (senza campi `_…`, senza righe nuove vuote). */
  data: Oggetto
  /** Per ogni lista, la chiave `_k` della riga inviata in ciascuna posizione. */
  mappe: Record<string, string[]>
}

/** Prepara i dati della pagina per il server. */
export function prepara(dati: unknown, righeVuote: OpzioniModuloDiario['righeVuote'] = {}): DatiPreparati {
  const data: Oggetto = {}
  const mappe: Record<string, string[]> = {}
  if (!eOggetto(dati)) return { data, mappe }
  for (const [campo, valore] of Object.entries(dati)) {
    if (campo.startsWith('_')) continue
    if (Array.isArray(valore)) {
      const vuota = righeVuote[campo]
      const righe: Oggetto[] = []
      const chiavi: string[] = []
      for (const r of valore) {
        if (!eOggetto(r)) continue
        if (r.id == null && vuota?.(r)) continue
        righe.push(Object.fromEntries(Object.entries(r).filter(([k]) => !k.startsWith('_'))))
        chiavi.push(String(r._k ?? ''))
      }
      data[campo] = righe
      mappe[campo] = chiavi
    } else {
      data[campo] = valore
    }
  }
  return { data, mappe }
}

export const serializza = (v: unknown): string => JSON.stringify(v)

/**
 * Dopo un salvataggio: assegna alle righe inviate senza `id` (o con un `id` che il server non
 * ha più) l'`id` che il server ha dato loro, sia nella copia inviata sia nelle righe della
 * pagina (per chiave `_k`). Le righe nuove si abbinano per contenuto, poi per ordine.
 */
export function unisciId(locale: unknown, inviato: Oggetto, risposta: unknown, mappe: Record<string, string[]>): void {
  if (!eOggetto(risposta)) return
  for (const [lista, chiavi] of Object.entries(mappe)) {
    const inviate = inviato[lista]
    const ricevute = risposta[lista]
    if (!Array.isArray(inviate) || !Array.isArray(ricevute)) continue
    const righeInviate = inviate as Riga[]
    const righeRicevute = (ricevute as unknown[]).filter(eOggetto) as Riga[]
    const idRicevuti = new Set<unknown>(righeRicevute.map((r) => r.id))
    const idInviati = new Set<unknown>(righeInviate.map((r) => r.id).filter((id) => id != null))
    // Righe inviate senza un id che il server conosce, con la loro posizione
    type Orfana = { riga: Riga; i: number }
    const orfane: Orfana[] = righeInviate
      .map((riga, i) => ({ riga, i }))
      .filter(({ riga }) => riga.id == null || !idRicevuti.has(riga.id))
    const nuove = righeRicevute.filter((r) => r.id != null && !idInviati.has(r.id))
    const usate = new Set<Riga>()
    const abbinamenti: (Orfana & { ricevuta: Riga })[] = []
    const stessoContenuto = (a: Riga, b: Riga) =>
      Object.keys(a).every((k) => k === 'id' || String(a[k] ?? '') === String(b[k] ?? ''))
    const senzaAbbinamento: Orfana[] = []
    for (const o of orfane) {
      const ricevuta = nuove.find((n) => !usate.has(n) && stessoContenuto(o.riga, n))
      if (ricevuta) {
        usate.add(ricevuta)
        abbinamenti.push({ ...o, ricevuta })
      } else senzaAbbinamento.push(o)
    }
    const restanti = nuove.filter((n) => !usate.has(n))
    for (const o of senzaAbbinamento) {
      const ricevuta = restanti.shift()
      if (ricevuta) abbinamenti.push({ ...o, ricevuta })
    }
    const righeLocali = eOggetto(locale) && Array.isArray(locale[lista]) ? (locale[lista] as Riga[]) : []
    for (const { riga, i, ricevuta } of abbinamenti) {
      riga.id = ricevuta.id
      const rigaLocale = righeLocali.find((l) => l._k === chiavi[i])
      if (rigaLocale) rigaLocale.id = ricevuta.id
    }
  }
}

/** Errori del server (liste indicizzate per posizione) → errori per chiave di riga `_k`. */
export function rimappaErrori(errori: unknown, mappe: Record<string, string[]>): ErroriModulo {
  const risultato: ErroriModulo = {}
  if (!eOggetto(errori)) return risultato
  for (const [campo, valore] of Object.entries(errori)) {
    if (Array.isArray(valore)) {
      risultato[campo] = valore.map(String)
    } else if (eOggetto(valore)) {
      const perRiga: Record<string, Record<string, string[]>> = {}
      for (const [indice, erroriRiga] of Object.entries(valore)) {
        const chiave = mappe[campo]?.[Number(indice)] ?? indice
        perRiga[chiave] = Object.fromEntries(
          Object.entries(eOggetto(erroriRiga) ? erroriRiga : {}).map(([k, v]) => [k, Array.isArray(v) ? v.map(String) : [String(v)]]),
        )
      }
      risultato[campo] = perRiga
    }
  }
  return risultato
}

function chiaveCasuale(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

/** Errori dopo i quali l'esito sul server è incerto: si ripete lo stesso invio con la stessa chiave. */
const transitorio = (e: ErroreApi) => e.stato === 0 || e.stato === 429 || e.stato >= 500

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

interface Tentativo {
  scrittura: ScritturaModulo
  /** Firma del corpo: stesso corpo → stessa chiave. */
  firma: string
  inviato: Oggetto
  mappe: Record<string, string[]>
}

export function useModuloDiario<T extends object>(
  diarioId: MaybeRefOrGetter<number | string>,
  percorsoModulo: MaybeRefOrGetter<string>,
  opzioni: OpzioniModuloDiario = {},
) {
  const {
    ritardoMs = 1500,
    autosave = true,
    righeVuote = {},
    trasporto = trasportoRete,
    ritentaMs = [2000, 5000, 15000, 30000, 60000],
    generaChiave = chiaveCasuale,
    eventiFinestra = true,
  } = opzioni
  // Il percorso si legge una volta: per un altro diario/modulo si crea un'altra istanza.
  const percorso = `/diari/${toValue(diarioId)}/${toValue(percorsoModulo)}`
  const solaLettura = () => Boolean(toValue(opzioni.solaLettura))

  const dati = ref(null) as Ref<T | null>
  const versione = ref(0)
  const caricamento = ref(false)
  const erroreCaricamento = ref('')
  const stato = ref<StatoSalvataggio>('salvato')
  const errore = ref('')
  const errori = ref<ErroriModulo>({})
  const conflitto = ref<{ versioneServer: number } | null>(null)
  const ultimoSalvataggio = ref<Date | null>(null)
  /** Ripetizione automatica programmata dopo un errore di rete/server. */
  const inRipetizione = ref(false)
  /** Ci sono modifiche della pagina non ancora confermate dal server. */
  const sporco = ref(false)

  /** Serializzazione di ciò che il server ha (ultimo caricamento o salvataggio riuscito). */
  let base = ''
  let timerDebounce: ReturnType<typeof setTimeout> | null = null
  let timerRitenta: ReturnType<typeof setTimeout> | null = null
  let tentativiFalliti = 0
  /** Invio con esito incerto (rete/5xx): va ripetuto con la stessa chiave prima di altri. */
  let incerto: Tentativo | null = null
  let inVolo: Promise<boolean> | null = null

  const testoCorrente = () => serializza(prepara(dati.value, righeVuote).data)

  function fermaTimer(): void {
    if (timerDebounce) clearTimeout(timerDebounce)
    timerDebounce = null
  }
  function fermaRitenta(): void {
    if (timerRitenta) clearTimeout(timerRitenta)
    timerRitenta = null
    inRipetizione.value = false
  }

  function programma(): void {
    if (!autosave || solaLettura()) return
    fermaTimer()
    timerDebounce = setTimeout(() => {
      timerDebounce = null
      void salva()
    }, ritardoMs)
  }

  watch(
    dati,
    () => {
      if (dati.value === null || caricamento.value) return
      sporco.value = testoCorrente() !== base
      if (inVolo) {
        if (sporco.value) programma()
        return
      }
      if (stato.value === 'conflitto') return
      if (!sporco.value) {
        if (stato.value === 'da_salvare') stato.value = 'salvato'
        fermaTimer()
        return
      }
      if (incerto && stato.value === 'errore') {
        // Le modifiche partono insieme alla ripetizione dell'invio incerto.
        fermaRitenta()
      }
      stato.value = 'da_salvare'
      programma()
    },
    { deep: true },
  )

  async function carica(): Promise<boolean> {
    fermaTimer()
    fermaRitenta()
    caricamento.value = true
    erroreCaricamento.value = ''
    try {
      const risposta = await trasporto.leggi(percorso)
      dati.value = conChiavi(risposta.data as T)
      versione.value = risposta.version ?? 0
      base = testoCorrente()
      sporco.value = false
      stato.value = 'salvato'
      errore.value = ''
      errori.value = {}
      conflitto.value = null
      incerto = null
      tentativiFalliti = 0
      return true
    } catch (e) {
      erroreCaricamento.value = e instanceof Error ? e.message : 'Errore imprevisto.'
      return false
    } finally {
      caricamento.value = false
    }
  }

  function nuovoTentativo(): Tentativo {
    const { data, mappe } = prepara(dati.value, righeVuote)
    const corpo = { version: versione.value, data }
    return { scrittura: { percorso, corpo, chiave: generaChiave() }, firma: serializza(corpo), inviato: data, mappe }
  }

  /** Invia un tentativo; aggiorna versione, id delle righe nuove, stato ed errori. */
  async function invia(t: Tentativo): Promise<boolean> {
    stato.value = 'salvataggio'
    try {
      const risposta = await trasporto.scrivi(t.scrittura)
      incerto = null
      tentativiFalliti = 0
      versione.value = risposta.version ?? versione.value + 1
      unisciId(dati.value, t.inviato, risposta.data, t.mappe)
      base = serializza(t.inviato)
      sporco.value = testoCorrente() !== base
      errore.value = ''
      errori.value = {}
      conflitto.value = null
      ultimoSalvataggio.value = new Date()
      stato.value = sporco.value ? 'da_salvare' : 'salvato'
      opzioni.dopoSalvataggio?.(risposta)
      return true
    } catch (e) {
      if (!(e instanceof ErroreApi)) {
        stato.value = 'errore'
        errore.value = e instanceof Error ? e.message : 'Errore imprevisto.'
        return false
      }
      const corpo = (e.corpo ?? {}) as { server_version?: number; error?: string; errors?: unknown; errori?: unknown }
      if (transitorio(e)) {
        incerto = t
        stato.value = 'errore'
        errore.value = e.offline ? 'Non salvato: sei offline o il server non risponde.' : e.message
        programmaRitenta()
        return false
      }
      incerto = null
      if (e.stato === 409) {
        conflitto.value = { versioneServer: Number(corpo.server_version ?? versione.value) }
        stato.value = 'conflitto'
        errore.value = 'Il modulo è stato modificato da un altro dispositivo o da un\'altra persona.'
        return false
      }
      const erroriServer = corpo.error === 'validation' ? corpo.errors : corpo.errori
      const mappati = rimappaErrori(erroriServer, t.mappe)
      if ((e.stato === 400 || e.stato === 422) && Object.keys(mappati).length) {
        errori.value = mappati
        stato.value = 'non_valido'
        errore.value = 'Alcuni campi non sono validi: correggili per salvare.'
        return false
      }
      stato.value = 'errore'
      errore.value = e.message
      return false
    }
  }

  function programmaRitenta(): void {
    fermaRitenta()
    const attesa = ritentaMs[Math.min(tentativiFalliti, ritentaMs.length - 1)] ?? 5000
    tentativiFalliti += 1
    inRipetizione.value = true
    timerRitenta = setTimeout(() => {
      timerRitenta = null
      inRipetizione.value = false
      void salva()
    }, attesa)
  }

  async function ciclo(): Promise<boolean> {
    if (incerto) {
      const ripeti = incerto
      const firmaCorrente = serializza({ version: versione.value, data: prepara(dati.value, righeVuote).data })
      if (firmaCorrente === ripeti.firma) return invia(ripeti)
      // Prima l'invio incerto (stessa chiave: se il server l'ha già applicato risponde uguale),
      // poi le modifiche successive con la versione aggiornata.
      if (!(await invia(ripeti))) return false
    }
    if (testoCorrente() === base) {
      sporco.value = false
      stato.value = 'salvato'
      return true
    }
    return invia(nuovoTentativo())
  }

  /**
   * Unico punto di scrittura del modulo. Con `nuoviDati` li sostituisce a quelli della pagina
   * e li salva subito; senza, salva i dati correnti (se diversi da quelli sul server).
   * Durante un conflitto non scrive: usare `ricarica()` o `sovrascrivi()`.
   */
  async function salva(nuoviDati?: T): Promise<boolean> {
    if (nuoviDati !== undefined) dati.value = conChiavi(nuoviDati)
    if (solaLettura() || dati.value === null) return false
    fermaTimer()
    if (inVolo) return inVolo.then(() => salva())
    if (conflitto.value) return false
    fermaRitenta()
    inVolo = ciclo().finally(() => {
      inVolo = null
    })
    return inVolo
  }

  /** Salva subito ciò che è in attesa (uscita dalla pagina, app in background). */
  async function salvaOra(): Promise<boolean> {
    fermaTimer()
    if (inVolo) return inVolo.then(() => (sporco.value || incerto ? salva() : true))
    if (conflitto.value || dati.value === null) return !sporco.value
    if (sporco.value || incerto) return salva()
    return true
  }

  /** Ripete subito l'ultimo salvataggio non riuscito. */
  function ripeti(): Promise<boolean> {
    tentativiFalliti = 0
    return salva()
  }

  /** Conflitto: scarta le modifiche locali e ricarica il modulo dal server. */
  function ricarica(): Promise<boolean> {
    return carica()
  }

  /** Conflitto: salva comunque i dati della pagina sopra la versione del server. */
  function sovrascrivi(): Promise<boolean> {
    if (!conflitto.value) return salva()
    versione.value = conflitto.value.versioneServer
    conflitto.value = null
    errore.value = ''
    return salva()
  }

  /** Errori di un campo di primo livello. */
  function erroriDi(campo: string): string[] {
    const v = errori.value[campo]
    return Array.isArray(v) ? v : []
  }

  /** Errori per campo di una riga di una lista (per chiave `_k`). */
  function erroriRiga(lista: string, riga: { _k?: string }): Record<string, string[]> {
    const v = errori.value[lista]
    return !Array.isArray(v) && v && riga._k ? (v[riga._k] ?? {}) : {}
  }

  if (eventiFinestra && typeof window !== 'undefined' && getCurrentScope()) {
    const allaVisibilita = () => {
      if (document.visibilityState === 'hidden') void salvaOra()
    }
    const allUscita = () => void salvaOra()
    const primaDiChiudere = (e: BeforeUnloadEvent) => {
      if (!sporco.value && !inVolo && !incerto) return
      void salvaOra()
      e.preventDefault()
    }
    const allaRete = () => {
      if (incerto || stato.value === 'errore') void ripeti()
    }
    document.addEventListener('visibilitychange', allaVisibilita)
    window.addEventListener('pagehide', allUscita)
    window.addEventListener('beforeunload', primaDiChiudere)
    window.addEventListener('online', allaRete)
    onScopeDispose(() => {
      document.removeEventListener('visibilitychange', allaVisibilita)
      window.removeEventListener('pagehide', allUscita)
      window.removeEventListener('beforeunload', primaDiChiudere)
      window.removeEventListener('online', allaRete)
    })
  }
  if (getCurrentScope()) {
    onScopeDispose(() => {
      // Pagina smontata con modifiche in attesa: ultimo tentativo, poi niente più timer.
      const daInviare = sporco.value && !conflitto.value
      fermaTimer()
      fermaRitenta()
      if (daInviare && !solaLettura()) void salva()
    })
  }

  return {
    percorso,
    dati,
    versione,
    caricamento,
    erroreCaricamento,
    stato,
    errore,
    errori,
    conflitto,
    ultimoSalvataggio,
    inRipetizione,
    sporco,
    carica,
    salva,
    salvaOra,
    ripeti,
    ricarica,
    sovrascrivi,
    erroriDi,
    erroriRiga,
  }
}

export type ModuloDiario<T extends object> = ReturnType<typeof useModuloDiario<T>>
