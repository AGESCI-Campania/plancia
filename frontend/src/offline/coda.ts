/**
 * Coda delle modifiche fatte offline (outbox): moduli del diario e foto. Ogni voce conserva la
 * sua `Idempotency-Key`, quindi un invio ripetuto (rete caduta a metà) non crea doppioni.
 *
 * - `trasportoOffline` è il trasporto dei moduli (`useModuloDiario`): prova la rete; se si è
 *   offline o il server non risponde mette la scrittura in coda e la pagina continua come se
 *   fosse salvata (sul dispositivo). Una modifica successiva dello stesso modulo sostituisce
 *   quella in coda: si invia sempre l'ultima versione.
 * - `inviaFotoOffline` fa lo stesso per le foto (`useGalleriaFoto`).
 * - `sincronizzaCoda` invia la coda in ordine, alla riconnessione, quando l'app torna in
 *   primo piano e ogni minuto finché resta qualcosa. Conflitti (409) e dati rifiutati (400/422)
 *   restano in coda: li risolve l'utente dalla pagina del modulo (`ModificheOffline.vue`).
 */
import { liveQuery } from 'dexie'
import { computed, ref } from 'vue'

import { ErroreApi } from '@/api/http'
import type { Allegato } from '@/composables/diarioCompilazione'
import { inviaFotoRete, type InviaFoto } from '@/composables/fotoDiario'
import { trasportoRete, type ModuloVersionato, type TrasportoModulo } from '@/composables/moduloDiario'

import { db, type VoceCoda } from './db'
import { aggiornaCopia, leggiConCopia } from './letture'

/** Tutte le voci in coda, aggiornate da IndexedDB (anche da altre schede). */
export const voci = ref<VoceCoda[]>([])
liveQuery(() => db.coda.orderBy('id').toArray()).subscribe({
  next: (tutte) => (voci.value = tutte),
  error: () => (voci.value = []),
})

/** Modifiche (moduli, foto) non ancora inviate al server, conflitti compresi. */
export const inAttesa = computed(() => voci.value.length)
/** Voci che richiedono una scelta dell'utente. */
export const daRisolvere = computed(() => voci.value.filter((v) => v.stato !== 'attesa'))
export const sincronizzazioneInCorso = ref(false)

/** La foto è stata salvata sul dispositivo: verrà inviata alla riconnessione. */
export class FotoInCoda extends Error {
  constructor() {
    super('Foto salvata sul dispositivo: verrà inviata quando torni online.')
    this.name = 'FotoInCoda'
  }
}

const transitorio = (e: unknown) => e instanceof ErroreApi && (e.offline || e.stato >= 500 || e.stato === 429)
const chiaveCasuale = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
const diarioDi = (percorso: string) => /^\/diari\/([^/]+)\//.exec(percorso)?.[1] ?? ''

// --- Versioni ------------------------------------------------------------------------------
// Una scrittura messa in coda lascia la pagina sulla sua versione di partenza X; quando la coda
// la invia il server risponde con Y. Le scritture successive della pagina (ancora con X) vanno
// rimappate su Y, altrimenti il server le rifiuterebbe come conflitto con sé stesse.
type MappaVersioni = Record<string, { da: number; a: number }>

async function versioni(): Promise<MappaVersioni> {
  return ((await db.meta.get('versioni'))?.valore as MappaVersioni | undefined) ?? {}
}
async function ricordaVersione(percorso: string, da: number, a: number): Promise<void> {
  const mappa = await versioni()
  mappa[percorso] = { da, a }
  await db.meta.put({ chiave: 'versioni', valore: mappa })
}
async function versioneAttuale(percorso: string, version: number): Promise<number> {
  const r = (await versioni())[percorso]
  return r && r.da === version ? r.a : version
}

// --- Moduli ----------------------------------------------------------------------------------
async function inCodaPer(percorso: string): Promise<VoceCoda | undefined> {
  return db.coda.where('percorso').equals(percorso).filter((v) => v.tipo === 'modulo').first()
}

export const trasportoOffline: TrasportoModulo = {
  async leggi(percorso) {
    const { dati } = await leggiConCopia(percorso, () => trasportoRete.leggi(percorso))
    // Modifiche fatte offline e non ancora inviate: la pagina mostra quelle.
    const voce = await inCodaPer(percorso)
    if (voce?.stato === 'attesa' && voce.corpo) return { version: voce.corpo.version, data: voce.corpo.data }
    return dati
  },

  async scrivi(s) {
    const version = await versioneAttuale(s.percorso, s.corpo.version)
    const corpo = { ...s.corpo, version }
    const fittizia: ModuloVersionato = { version: s.corpo.version, data: s.corpo.data }
    const inCoda = await inCodaPer(s.percorso)
    if (inCoda?.stato === 'attesa') {
      // C'è già una versione in coda: la si sostituisce (stessa versione di partenza) e si
      // prova a inviare tutto in ordine.
      await db.coda.update(inCoda.id!, { corpo: { version: inCoda.corpo!.version, data: corpo.data }, chiave: s.chiave })
      void sincronizzaCoda()
      return fittizia
    }
    try {
      const risposta = await trasportoRete.scrivi({ ...s, corpo })
      await aggiornaCopia(s.percorso, risposta)
      return risposta
    } catch (e) {
      if (!transitorio(e)) throw e
      await db.coda.add({
        tipo: 'modulo',
        diarioId: diarioDi(s.percorso),
        percorso: s.percorso,
        chiave: s.chiave,
        corpo,
        stato: 'attesa',
        creatoAt: Date.now(),
        tentativi: 0,
      })
      return fittizia
    }
  },
}

/** Applica alla pagina le modifiche offline in conflitto/rifiutate e le toglie dalla coda. */
export async function recuperaModificheModulo(voce: VoceCoda): Promise<unknown> {
  await db.coda.delete(voce.id!)
  return voce.corpo?.data
}

export async function scartaVoce(voce: VoceCoda): Promise<void> {
  await db.coda.delete(voce.id!)
}

// --- Foto ------------------------------------------------------------------------------------
export const inviaFotoOffline: InviaFoto = async (invio, opzioni) => {
  try {
    return await inviaFotoRete(invio, opzioni)
  } catch (e) {
    if (!transitorio(e)) throw e
    await db.coda.add({
      tipo: 'foto',
      diarioId: String(invio.diarioId),
      percorso: `/diari/${invio.diarioId}/allegati`,
      chiave: invio.chiave,
      modulo: invio.modulo,
      file: invio.file,
      nome: invio.nome,
      stato: 'attesa',
      creatoAt: Date.now(),
      tentativi: 0,
    })
    throw new FotoInCoda()
  }
}

/** Foto in coda per un diario e un modulo (anteprime per la galleria). */
export function fotoInCoda(diarioId: string | number, modulo: string): VoceCoda[] {
  return voci.value.filter((v) => v.tipo === 'foto' && v.diarioId === String(diarioId) && v.modulo === modulo)
}

// --- Sincronizzazione --------------------------------------------------------------------------
/** Esito dell'invio di una voce: `continua` = passa alla successiva, `ferma` = rete/sessione giù. */
async function inviaVoce(voce: VoceCoda): Promise<'continua' | 'ferma'> {
  try {
    if (voce.tipo === 'modulo') {
      const version = await versioneAttuale(voce.percorso, voce.corpo!.version)
      const risposta = await trasportoRete.scrivi({
        percorso: voce.percorso,
        corpo: { version, data: voce.corpo!.data },
        chiave: voce.chiave,
      })
      if (risposta.version !== null) await ricordaVersione(voce.percorso, voce.corpo!.version, risposta.version)
      await aggiornaCopia(voce.percorso, risposta)
    } else {
      await inviaFotoRete({
        diarioId: voce.diarioId,
        modulo: voce.modulo ?? '',
        file: voce.file!,
        nome: voce.nome ?? 'foto.jpg',
        chiave: voce.chiave,
      }) satisfies Allegato
    }
    await db.coda.delete(voce.id!)
    return 'continua'
  } catch (e) {
    if (!(e instanceof ErroreApi) || transitorio(e) || e.stato === 401) {
      // Rete, server o sessione scaduta: si riprova più tardi (dopo un nuovo accesso).
      await db.coda.update(voce.id!, { tentativi: voce.tentativi + 1 })
      return 'ferma'
    }
    const stato = e.stato === 409 ? 'conflitto' : e.stato === 400 || e.stato === 422 ? 'non_valido' : 'rifiutata'
    await db.coda.update(voce.id!, { stato, errore: e.message, tentativi: voce.tentativi + 1 })
    return 'continua'
  }
}

let inCorso: Promise<number> | null = null

/** Invia la coda in ordine; restituisce quante voci restano da inviare. */
export function sincronizzaCoda(): Promise<number> {
  inCorso ??= (async () => {
    sincronizzazioneInCorso.value = true
    try {
      for (;;) {
        const prossima = await db.coda.where('stato').equals('attesa').sortBy('id')
        if (!prossima.length) break
        let fermato = false
        for (const voce of prossima) {
          if ((await inviaVoce(voce)) === 'ferma') {
            fermato = true
            break
          }
        }
        if (fermato) break
      }
      return await db.coda.where('stato').equals('attesa').count()
    } finally {
      sincronizzazioneInCorso.value = false
      inCorso = null
    }
  })()
  return inCorso
}

let avviata = false

/** Riprova da solo: alla riconnessione, al ritorno in primo piano, ogni minuto. */
export function avviaSincronizzazione(): void {
  if (avviata || typeof window === 'undefined') return
  avviata = true
  const prova = () => {
    if (navigator.onLine && voci.value.some((v) => v.stato === 'attesa')) void sincronizzaCoda()
  }
  window.addEventListener('online', prova)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') prova()
  })
  setInterval(prova, 60_000)
  prova()
}

// --- Utente e logout -----------------------------------------------------------------------------
/** Dopo l'accesso: se i dati locali sono di un altro utente si cancellano. */
export async function associaUtente(id: number): Promise<void> {
  const precedente = (await db.meta.get('utente'))?.valore
  if (precedente !== undefined && precedente !== id) await svuotaDatiOffline()
  await db.meta.put({ chiave: 'utente', valore: id })
  avviaSincronizzazione()
}

/** Sessione scaduta: via le copie delle letture, resta solo ciò che non è stato inviato. */
export async function dimenticaLetture(): Promise<void> {
  await db.letture.clear()
}

/** Logout: si cancella tutto (dati di minori sul dispositivo, decisione 5 del piano). */
export async function svuotaDatiOffline(): Promise<void> {
  await Promise.all([db.letture.clear(), db.coda.clear(), db.meta.clear()])
}

export { chiaveCasuale as nuovaChiave }
