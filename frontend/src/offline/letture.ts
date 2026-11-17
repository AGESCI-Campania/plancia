/**
 * Letture con copia locale: prima la rete; se si è offline (o il server non risponde) si usa
 * l'ultima copia salvata. Solo per i dati che servono a compilare i moduli offline.
 */
import { ErroreApi } from '@/api/http'

import { db } from './db'

export interface Letto<T> {
  dati: T
  /** Copia locale (offline): può non essere aggiornata. */
  copia: boolean
}

const transitorio = (e: unknown) => e instanceof ErroreApi && (e.offline || e.stato >= 500 || e.stato === 429)

export async function leggiConCopia<T>(url: string, leggi: () => Promise<T>): Promise<Letto<T>> {
  try {
    const dati = await leggi()
    await db.letture.put({ url, dati, salvatoAt: Date.now() }).catch(() => undefined)
    return { dati, copia: false }
  } catch (e) {
    if (!transitorio(e)) throw e
    const salvata = await db.letture.get(url).catch(() => undefined)
    if (!salvata) throw e
    return { dati: salvata.dati as T, copia: true }
  }
}

/** Aggiorna la copia senza rete (es. dopo un salvataggio messo in coda). */
export async function aggiornaCopia(url: string, dati: unknown): Promise<void> {
  await db.letture.put({ url, dati, salvatoAt: Date.now() }).catch(() => undefined)
}
