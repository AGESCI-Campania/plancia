import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ErroreApi } from '@/api/http'

// Foto: l'invio di rete (XHR) è sostituito da un finto controllabile
const inviaFotoRete = vi.fn()
vi.mock('@/composables/fotoDiario', () => ({ inviaFotoRete: (...a: unknown[]) => inviaFotoRete(...a) }))

const { db } = await import('@/offline/db')
const coda = await import('@/offline/coda')

type Risposta = { status: number; body: unknown }
let rete: 'on' | 'off'
let risposte: Risposta[]
const chiamate: { url: string; init: RequestInit }[] = []

function rispondi(r: Risposta): Response {
  return new Response(JSON.stringify(r.body), { status: r.status, headers: { 'Content-Type': 'application/json' } })
}

beforeEach(async () => {
  await Promise.all([db.coda.clear(), db.letture.clear(), db.meta.clear()])
  rete = 'on'
  risposte = []
  chiamate.length = 0
  inviaFotoRete.mockReset()
  vi.stubGlobal('fetch', async (url: string, init: RequestInit = {}) => {
    chiamate.push({ url, init })
    if (rete === 'off') throw new TypeError('Failed to fetch')
    return rispondi(risposte.shift() ?? { status: 200, body: { version: 1, data: {} } })
  })
})
afterEach(() => vi.unstubAllGlobals())

const PERCORSO = '/diari/7/missione'
const scrittura = (version: number, nome: string, chiave = `k-${nome}`) => ({
  percorso: PERCORSO,
  corpo: { version, data: { nome } },
  chiave,
})

describe('trasportoOffline', () => {
  it('offline mette in coda e la lettura restituisce le modifiche locali', async () => {
    rete = 'off'
    const r = await coda.trasportoOffline.scrivi(scrittura(3, 'a'))
    expect(r).toEqual({ version: 3, data: { nome: 'a' } })
    expect(await db.coda.count()).toBe(1)

    await db.letture.put({ url: PERCORSO, dati: { version: 3, data: { nome: 'server' } }, salvatoAt: 0 })
    expect(await coda.trasportoOffline.leggi(PERCORSO)).toEqual({ version: 3, data: { nome: 'a' } })
  })

  it("una modifica successiva sostituisce quella in coda (si invia sempre l'ultima)", async () => {
    rete = 'off'
    await coda.trasportoOffline.scrivi(scrittura(3, 'a'))
    await coda.trasportoOffline.scrivi(scrittura(3, 'b'))
    const voci = await db.coda.toArray()
    expect(voci).toHaveLength(1)
    expect(voci[0]!.corpo).toEqual({ version: 3, data: { nome: 'b' } })
    expect(voci[0]!.chiave).toBe('k-b')
  })

  it('la sincronizzazione invia con la stessa chiave e rimappa la versione della pagina', async () => {
    rete = 'off'
    await coda.trasportoOffline.scrivi(scrittura(3, 'a', 'chiave-1'))
    rete = 'on'
    risposte = [{ status: 200, body: { version: 4, data: { nome: 'a' } } }]
    expect(await coda.sincronizzaCoda()).toBe(0)
    expect(await db.coda.count()).toBe(0)
    const invio = chiamate.at(-1)!
    expect((invio.init.headers as Record<string, string>)['Idempotency-Key']).toBe('chiave-1')
    expect(JSON.parse(invio.init.body as string).version).toBe(3)

    // La pagina è rimasta alla versione 3: il salvataggio successivo parte dalla 4
    risposte = [{ status: 200, body: { version: 5, data: { nome: 'c' } } }]
    await coda.trasportoOffline.scrivi(scrittura(3, 'c'))
    expect(JSON.parse(chiamate.at(-1)!.init.body as string).version).toBe(4)
  })

  it('un conflitto alla sincronizzazione resta in coda da risolvere', async () => {
    rete = 'off'
    await coda.trasportoOffline.scrivi(scrittura(3, 'a'))
    rete = 'on'
    risposte = [{ status: 409, body: { error: 'conflict', server_version: 6 } }]
    expect(await coda.sincronizzaCoda()).toBe(0)
    const [voce] = await db.coda.toArray()
    expect(voce!.stato).toBe('conflitto')
    expect(await coda.recuperaModificheModulo(voce!)).toEqual({ nome: 'a' })
    expect(await db.coda.count()).toBe(0)
  })

  it('i rifiuti non transitori arrivano alla pagina (non vanno in coda)', async () => {
    risposte = [{ status: 409, body: { error: 'conflict' } }]
    await expect(coda.trasportoOffline.scrivi(scrittura(3, 'a'))).rejects.toBeInstanceOf(ErroreApi)
    expect(await db.coda.count()).toBe(0)
  })
})

describe('foto offline', () => {
  it('offline la foto resta sul dispositivo e parte alla sincronizzazione', async () => {
    inviaFotoRete.mockRejectedValueOnce(new ErroreApi(0, 'offline'))
    const invio = { diarioId: 7, modulo: 'impresa1', file: new Blob(['x']), nome: 'a.jpg', chiave: 'f1' }
    await expect(coda.inviaFotoOffline(invio)).rejects.toBeInstanceOf(coda.FotoInCoda)
    expect(await db.coda.count()).toBe(1)

    inviaFotoRete.mockResolvedValueOnce({ id: 1 })
    expect(await coda.sincronizzaCoda()).toBe(0)
    expect(inviaFotoRete.mock.calls.at(-1)![0]).toMatchObject({ chiave: 'f1', modulo: 'impresa1', nome: 'a.jpg' })
  })
})

describe('dati legati all’utente', () => {
  it('un altro utente cancella i dati locali, lo stesso li conserva', async () => {
    await coda.associaUtente(1)
    await db.coda.add({ tipo: 'modulo', diarioId: '7', percorso: PERCORSO, chiave: 'k', stato: 'attesa', creatoAt: 0, tentativi: 0 })
    await coda.associaUtente(1)
    expect(await db.coda.count()).toBe(1)
    await coda.associaUtente(2)
    expect(await db.coda.count()).toBe(0)
  })
})
