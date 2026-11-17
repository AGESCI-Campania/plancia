import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, type EffectScope } from 'vue'

import {
  nuovaRiga,
  prepara,
  rimappaErrori,
  unisciId,
  useModuloDiario,
  type OpzioniModuloDiario,
} from '@/composables/moduloDiario'

interface Membro {
  id: number | null
  nome: string
  ruolo: string
  sentiero: string
  _k?: string
}
interface Presentazione {
  cosa_sappiamo_fare: string
  membri: Membro[]
}

const json = (stato: number, corpo: unknown) =>
  new Response(JSON.stringify(corpo), { status: stato, headers: { 'Content-Type': 'application/json' } })

const fetchMock = vi.fn<typeof fetch>()

/** Corpo e intestazioni delle PUT fatte finora. */
function put(): { corpo: { version: number; data: Presentazione }; chiave: string; url: string }[] {
  return fetchMock.mock.calls
    .filter(([, init]) => init?.method === 'PUT')
    .map(([url, init]) => ({
      url: String(url),
      corpo: JSON.parse(String(init?.body)),
      chiave: (init?.headers as Record<string, string>)['Idempotency-Key'] as string,
    }))
}

let scope: EffectScope

function crea(opzioni: OpzioniModuloDiario = {}) {
  scope = effectScope()
  let chiave = 0
  return scope.run(() =>
    useModuloDiario<Presentazione>(7, 'presentazione', {
      ritardoMs: 1000,
      ritentaMs: [2000, 4000],
      generaChiave: () => `k${++chiave}`,
      righeVuote: { membri: (r) => !String(r.nome ?? '').trim() },
      ...opzioni,
    }),
  )!
}

/** Lascia girare watcher, timer e promesse fino a `ms`. */
async function avanza(ms = 0): Promise<void> {
  await nextTick()
  await vi.advanceTimersByTimeAsync(ms)
  await nextTick()
}

const iniziale = { version: 3, data: { cosa_sappiamo_fare: 'Nodi', membri: [{ id: 1, nome: 'Anna', ruolo: 'csq', sentiero: 'scoperta' }] } }

async function caricato(opzioni: OpzioniModuloDiario = {}) {
  fetchMock.mockResolvedValueOnce(json(200, iniziale))
  const m = crea(opzioni)
  await m.carica()
  await avanza()
  return m
}

beforeEach(() => {
  vi.useFakeTimers()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  document.cookie = 'csrftoken=tok'
})

afterEach(() => {
  scope?.stop()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('caricamento', () => {
  it('legge il modulo con versione e chiavi di riga, senza scrivere', async () => {
    const m = await caricato()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]![0])).toBe('/api/v1/diari/7/presentazione')
    expect(m.versione.value).toBe(3)
    expect(m.dati.value?.membri[0]!._k).toMatch(/^r\d+/)
    expect(m.stato.value).toBe('salvato')
    expect(m.sporco.value).toBe(false)
    await avanza(5000)
    expect(put()).toHaveLength(0)
  })

  it('errore di caricamento', async () => {
    fetchMock.mockResolvedValueOnce(json(403, { detail: 'Accesso non consentito' }))
    const m = crea()
    expect(await m.carica()).toBe(false)
    expect(m.erroreCaricamento.value).toBe('Accesso non consentito')
  })
})

describe('autosave con debounce', () => {
  it('più modifiche ravvicinate → una sola PUT dopo il ritardo, con Idempotency-Key e CSRF', async () => {
    const m = await caricato()
    m.dati.value!.cosa_sappiamo_fare = 'N'
    await avanza(400)
    m.dati.value!.cosa_sappiamo_fare = 'No'
    await avanza(400)
    m.dati.value!.cosa_sappiamo_fare = 'Nodi e tende'
    await avanza()
    expect(m.stato.value).toBe('da_salvare')
    expect(m.sporco.value).toBe(true)
    expect(put()).toHaveLength(0)

    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { cosa_sappiamo_fare: 'Nodi e tende', membri: iniziale.data.membri } }))
    await avanza(999)
    expect(put()).toHaveLength(0)
    await avanza(1)
    expect(put()).toHaveLength(1)
    const p = put()[0]!
    expect(p.url).toBe('/api/v1/diari/7/presentazione')
    expect(p.chiave).toBe('k1')
    expect(p.corpo.version).toBe(3)
    expect(p.corpo.data.cosa_sappiamo_fare).toBe('Nodi e tende')
    expect(p.corpo.data.membri[0]!).toEqual({ id: 1, nome: 'Anna', ruolo: 'csq', sentiero: 'scoperta' })
    const init = fetchMock.mock.calls[1]![1]!
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('tok')
    await avanza()
    expect(m.stato.value).toBe('salvato')
    expect(m.versione.value).toBe(4)
    expect(m.sporco.value).toBe(false)
    expect(m.ultimoSalvataggio.value).toBeInstanceOf(Date)
  })

  it('tornando ai dati del server non salva', async () => {
    const m = await caricato()
    m.dati.value!.cosa_sappiamo_fare = 'Altro'
    await avanza(300)
    m.dati.value!.cosa_sappiamo_fare = 'Nodi'
    await avanza(2000)
    expect(put()).toHaveLength(0)
    expect(m.stato.value).toBe('salvato')
  })

  it('senza autosave salva solo su richiesta', async () => {
    const m = await caricato({ autosave: false })
    m.dati.value!.cosa_sappiamo_fare = 'X'
    await avanza(5000)
    expect(put()).toHaveLength(0)
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'X' } }))
    expect(await m.salva()).toBe(true)
    expect(put()).toHaveLength(1)
  })

  it('in sola lettura non scrive mai', async () => {
    const m = await caricato({ solaLettura: true })
    m.dati.value!.cosa_sappiamo_fare = 'X'
    await avanza(5000)
    expect(await m.salva()).toBe(false)
    expect(put()).toHaveLength(0)
  })

  it('salvaOra invia subito senza aspettare il debounce', async () => {
    const m = await caricato()
    m.dati.value!.cosa_sappiamo_fare = 'Subito'
    await avanza()
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'Subito' } }))
    expect(await m.salvaOra()).toBe(true)
    expect(put()).toHaveLength(1)
    await avanza(3000)
    expect(put()).toHaveLength(1)
  })

  it("l'app in background (visibilitychange) salva le modifiche in attesa", async () => {
    const m = await caricato()
    m.dati.value!.cosa_sappiamo_fare = 'Background'
    await avanza()
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'Background' } }))
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await avanza()
    expect(put()).toHaveLength(1)
    expect(m.stato.value).toBe('salvato')
  })

  it('modifiche durante un invio partono dopo, con la versione aggiornata', async () => {
    const m = await caricato()
    let rispondi!: (r: Response) => void
    fetchMock.mockImplementationOnce(() => new Promise<Response>((r) => (rispondi = r)))
    m.dati.value!.cosa_sappiamo_fare = 'Primo'
    await avanza(1000)
    expect(m.stato.value).toBe('salvataggio')
    m.dati.value!.cosa_sappiamo_fare = 'Secondo'
    await avanza(1000)
    expect(put()).toHaveLength(1)
    fetchMock.mockResolvedValueOnce(json(200, { version: 5, data: { ...iniziale.data, cosa_sappiamo_fare: 'Secondo' } }))
    rispondi(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'Primo' } }))
    await avanza(1000)
    const invii = put()
    expect(invii).toHaveLength(2)
    expect(invii[1]!.corpo.version).toBe(4)
    expect(invii[1]!.corpo.data.cosa_sappiamo_fare).toBe('Secondo')
    expect(invii[1]!.chiave).not.toBe(invii[0]!.chiave)
    expect(m.versione.value).toBe(5)
    expect(m.stato.value).toBe('salvato')
  })
})

describe('righe ripetute', () => {
  it('non invia le righe nuove vuote e assegna gli id del server alle righe nuove', async () => {
    const m = await caricato()
    m.dati.value!.membri.push(nuovaRiga({ id: null, nome: '', ruolo: '', sentiero: 'non_specificato' }))
    await avanza(1000)
    expect(put()).toHaveLength(0) // solo una riga vuota: niente da salvare

    m.dati.value!.membri[1]!.nome = 'Bruno'
    m.dati.value!.membri.push(nuovaRiga({ id: null, nome: 'Carla', ruolo: '', sentiero: 'competenza' }))
    // Il server restituisce i membri in ordine alfabetico, con gli id nuovi
    fetchMock.mockResolvedValueOnce(
      json(200, {
        version: 4,
        data: {
          cosa_sappiamo_fare: 'Nodi',
          membri: [
            { id: 1, nome: 'Anna', ruolo: 'csq', sentiero: 'scoperta' },
            { id: 9, nome: 'Bruno', ruolo: '', sentiero: 'non_specificato' },
            { id: 8, nome: 'Carla', ruolo: '', sentiero: 'competenza' },
          ],
        },
      }),
    )
    await avanza(1000)
    expect(put()[0]!.corpo.data.membri.map((r) => r.id)).toEqual([1, null, null])
    expect(m.dati.value!.membri.map((r) => [r.nome, r.id])).toEqual([
      ['Anna', 1],
      ['Bruno', 9],
      ['Carla', 8],
    ])
    expect(m.stato.value).toBe('salvato')
    expect(m.sporco.value).toBe(false)

    // Il salvataggio successivo non duplica le righe: porta gli id
    fetchMock.mockResolvedValueOnce(json(200, { version: 5, data: iniziale.data }))
    m.dati.value!.membri.splice(0, 1)
    await avanza(1000)
    expect(put()[1]!.corpo.data.membri.map((r) => r.id)).toEqual([9, 8])
  })

  it('le modifiche fatte durante l’invio restano e ricevono gli id', async () => {
    const m = await caricato()
    let rispondi!: (r: Response) => void
    fetchMock.mockImplementationOnce(() => new Promise<Response>((r) => (rispondi = r)))
    m.dati.value!.membri.push(nuovaRiga({ id: null, nome: 'Dario', ruolo: '', sentiero: 'scoperta' }))
    await avanza(1000)
    m.dati.value!.membri[1]!.nome = 'Dario Rossi'
    rispondi(
      json(200, {
        version: 4,
        data: { ...iniziale.data, membri: [...iniziale.data.membri, { id: 5, nome: 'Dario', ruolo: '', sentiero: 'scoperta' }] },
      }),
    )
    fetchMock.mockResolvedValueOnce(json(200, { version: 5, data: iniziale.data }))
    await avanza()
    expect(m.dati.value!.membri[1]!).toMatchObject({ id: 5, nome: 'Dario Rossi' })
    expect(m.stato.value).toBe('da_salvare')
    await avanza(1000)
    expect(put()[1]!.corpo.data.membri[1]!).toEqual({ id: 5, nome: 'Dario Rossi', ruolo: '', sentiero: 'scoperta' })
  })
})

describe('conflitto (409)', () => {
  it('ferma l’autosave e permette di sovrascrivere con la versione del server', async () => {
    const m = await caricato()
    fetchMock.mockResolvedValueOnce(json(409, { error: 'conflict', server_version: 6 }))
    m.dati.value!.cosa_sappiamo_fare = 'Mio'
    await avanza(1000)
    expect(m.stato.value).toBe('conflitto')
    expect(m.conflitto.value).toEqual({ versioneServer: 6 })
    expect(m.errore.value).toMatch(/modificato/)

    m.dati.value!.cosa_sappiamo_fare = 'Mio ancora'
    await avanza(5000)
    expect(put()).toHaveLength(1) // niente autosave durante il conflitto
    expect(await m.salva()).toBe(false)

    fetchMock.mockResolvedValueOnce(json(200, { version: 7, data: { ...iniziale.data, cosa_sappiamo_fare: 'Mio ancora' } }))
    expect(await m.sovrascrivi()).toBe(true)
    const invii = put()
    expect(invii).toHaveLength(2)
    expect(invii[1]!.corpo.version).toBe(6)
    expect(invii[1]!.chiave).not.toBe(invii[0]!.chiave)
    expect(m.stato.value).toBe('salvato')
    expect(m.conflitto.value).toBeNull()
  })

  it('ricaricare scarta le modifiche locali', async () => {
    const m = await caricato()
    fetchMock.mockResolvedValueOnce(json(409, { error: 'conflict', server_version: 6 }))
    m.dati.value!.cosa_sappiamo_fare = 'Mio'
    await avanza(1000)
    fetchMock.mockResolvedValueOnce(json(200, { version: 6, data: { ...iniziale.data, cosa_sappiamo_fare: 'Del server' } }))
    expect(await m.ricarica()).toBe(true)
    await avanza(3000)
    expect(m.dati.value!.cosa_sappiamo_fare).toBe('Del server')
    expect(m.versione.value).toBe(6)
    expect(m.stato.value).toBe('salvato')
    expect(put()).toHaveLength(1)
  })
})

describe('errori di validazione', () => {
  it('400 dei moduli: errori per campo e per riga (per chiave di riga)', async () => {
    const m = await caricato()
    m.dati.value!.membri.push(nuovaRiga({ id: null, nome: 'X', ruolo: 'boh', sentiero: 'scoperta' }))
    fetchMock.mockResolvedValueOnce(
      json(400, {
        error: 'validation',
        errors: { cosa_sappiamo_fare: ['lunghezza massima 10000 caratteri'], membri: { '1': { ruolo: ['valore non valido'] } } },
      }),
    )
    await avanza(1000)
    expect(m.stato.value).toBe('non_valido')
    expect(m.erroriDi('cosa_sappiamo_fare')).toEqual(['lunghezza massima 10000 caratteri'])
    expect(m.erroriRiga('membri', m.dati.value!.membri[1]!)).toEqual({ ruolo: ['valore non valido'] })
    expect(m.erroriRiga('membri', m.dati.value!.membri[0]!)).toEqual({})
    expect(m.erroriDi('membri')).toEqual([])

    // Correggendo si riprova da soli e gli errori spariscono
    m.dati.value!.membri[1]!.ruolo = 'vcsq'
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: iniziale.data }))
    await avanza(1000)
    expect(put()).toHaveLength(2)
    expect(m.stato.value).toBe('salvato')
    expect(m.errori.value).toEqual({})
  })

  it('422 con `errori`: errori per campo', async () => {
    const m = await caricato()
    fetchMock.mockResolvedValueOnce(json(422, { detail: 'Dati non validi.', errori: { cosa_sappiamo_fare: ['Obbligatorio'] } }))
    m.dati.value!.cosa_sappiamo_fare = ''
    await avanza(1000)
    expect(m.stato.value).toBe('non_valido')
    expect(m.erroriDi('cosa_sappiamo_fare')).toEqual(['Obbligatorio'])
  })

  it('422 senza errori di campo (es. stato del diario): messaggio, nessuna ripetizione', async () => {
    const m = await caricato()
    fetchMock.mockResolvedValueOnce(json(422, { detail: 'La relazione non è ancora disponibile.' }))
    m.dati.value!.cosa_sappiamo_fare = 'Z'
    await avanza(1000)
    expect(m.stato.value).toBe('errore')
    expect(m.errore.value).toBe('La relazione non è ancora disponibile.')
    expect(m.inRipetizione.value).toBe(false)
    await avanza(10000)
    expect(put()).toHaveLength(1)
  })

  it('403: nessuna ripetizione automatica', async () => {
    const m = await caricato()
    fetchMock.mockResolvedValueOnce(json(403, { detail: 'Accesso non consentito' }))
    m.dati.value!.cosa_sappiamo_fare = 'Z'
    await avanza(1000)
    expect(m.stato.value).toBe('errore')
    await avanza(10000)
    expect(put()).toHaveLength(1)
  })
})

describe('ripetizione e idempotenza', () => {
  it('rete assente: ripete da solo lo stesso salvataggio con la stessa chiave', async () => {
    const m = await caricato()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    fetchMock.mockResolvedValueOnce(json(503, { detail: 'Manutenzione' }))
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'Offline' } }))
    m.dati.value!.cosa_sappiamo_fare = 'Offline'
    await avanza(1000)
    expect(m.stato.value).toBe('errore')
    expect(m.errore.value).toMatch(/offline/)
    expect(m.inRipetizione.value).toBe(true)
    expect(m.sporco.value).toBe(true)
    await avanza(2000) // primo ritento → 503
    expect(put()).toHaveLength(2)
    expect(m.stato.value).toBe('errore')
    await avanza(3999)
    expect(put()).toHaveLength(2)
    await avanza(1) // secondo ritento (4 s) → ok
    const invii = put()
    expect(invii).toHaveLength(3)
    expect(new Set(invii.map((i) => i.chiave))).toEqual(new Set(['k1']))
    expect(invii.every((i) => i.corpo.version === 3)).toBe(true)
    expect(m.stato.value).toBe('salvato')
    expect(m.versione.value).toBe(4)
  })

  it('ripeti() manuale riusa la chiave; un salvataggio nuovo ne usa un’altra', async () => {
    const m = await caricato()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    m.dati.value!.cosa_sappiamo_fare = 'A'
    await avanza(1000)
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'A' } }))
    expect(await m.ripeti()).toBe(true)
    fetchMock.mockResolvedValueOnce(json(200, { version: 5, data: { ...iniziale.data, cosa_sappiamo_fare: 'B' } }))
    m.dati.value!.cosa_sappiamo_fare = 'B'
    await avanza(1000)
    expect(put().map((i) => [i.chiave, i.corpo.version])).toEqual([
      ['k1', 3],
      ['k1', 3],
      ['k2', 4],
    ])
  })

  it('modifiche dopo un invio dall’esito incerto: prima si ripete quello, poi le nuove', async () => {
    const m = await caricato()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    m.dati.value!.cosa_sappiamo_fare = 'Uno'
    await avanza(1000)
    expect(m.stato.value).toBe('errore')
    // Il server aveva già applicato "Uno": con la stessa chiave risponde come la prima volta
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'Uno' } }))
    fetchMock.mockResolvedValueOnce(json(200, { version: 5, data: { ...iniziale.data, cosa_sappiamo_fare: 'Due' } }))
    m.dati.value!.cosa_sappiamo_fare = 'Due'
    await avanza()
    expect(m.inRipetizione.value).toBe(false) // il ritento parte con le nuove modifiche
    await avanza(1000)
    expect(put().map((i) => [i.chiave, i.corpo.version, i.corpo.data.cosa_sappiamo_fare])).toEqual([
      ['k1', 3, 'Uno'],
      ['k1', 3, 'Uno'],
      ['k2', 4, 'Due'],
    ])
    expect(m.versione.value).toBe(5)
    expect(m.stato.value).toBe('salvato')
  })

  it('tornata la rete (evento online) ripete subito', async () => {
    const m = await caricato()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    m.dati.value!.cosa_sappiamo_fare = 'Rete'
    await avanza(1000)
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'Rete' } }))
    window.dispatchEvent(new Event('online'))
    await avanza()
    expect(put()).toHaveLength(2)
    expect(put()[1]!.chiave).toBe('k1')
    expect(m.stato.value).toBe('salvato')
  })

  it('alla chiusura della pagina con modifiche in attesa salva', async () => {
    const m = await caricato()
    m.dati.value!.cosa_sappiamo_fare = 'Uscita'
    await avanza()
    fetchMock.mockResolvedValueOnce(json(200, { version: 4, data: { ...iniziale.data, cosa_sappiamo_fare: 'Uscita' } }))
    scope.stop()
    await avanza()
    expect(put()).toHaveLength(1)
  })
})

describe('funzioni pure', () => {
  it('prepara toglie i campi locali e le righe nuove vuote', () => {
    const r = prepara(
      { a: 1, _x: 2, l: [{ id: null, n: '', _k: 'r1' }, { id: 3, n: '', _k: 'r2' }, { id: null, n: 'x', _k: 'r3' }] },
      { l: (riga) => !riga.n },
    )
    expect(r.data).toEqual({ a: 1, l: [{ id: 3, n: '' }, { id: null, n: 'x' }] })
    expect(r.mappe).toEqual({ l: ['r2', 'r3'] })
  })

  it('unisciId abbina per contenuto e poi per ordine; rimappaErrori usa le chiavi', () => {
    const locale = { l: [{ _k: 'a', id: null, n: 'x' }, { _k: 'b', id: 77, n: 'y' }] }
    const inviato = { l: [{ id: null, n: 'x' }, { id: 77, n: 'y' }] }
    // La riga 77 non c'è più sul server (eliminata altrove): ricreata con un altro id
    unisciId(locale, inviato, { l: [{ id: 5, n: 'y' }, { id: 4, n: 'x' }] }, { l: ['a', 'b'] })
    expect(locale.l.map((r) => r.id)).toEqual([4, 5])
    expect(inviato.l.map((r) => r.id)).toEqual([4, 5])
    expect(rimappaErrori({ n: ['e'], l: { '1': { n: ['f'] } } }, { l: ['a', 'b'] })).toEqual({ n: ['e'], l: { b: { n: ['f'] } } })
  })
})
