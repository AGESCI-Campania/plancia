import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, type EffectScope } from 'vue'

import type { Allegato } from '@/composables/diarioCompilazione'
import { formattaDimensione, useGalleriaFoto, type InviaFoto } from '@/composables/fotoDiario'

vi.mock('@/composables/conferma', () => ({ conferma: vi.fn(async () => true) }))

const allegato = (id: number, nome = `foto${id}.jpg`): Allegato => ({
  id,
  modulo: 'impresa_1',
  nome,
  mime: 'image/jpeg',
  dimensione: 1000,
  stato_sync: 'locale',
  creato_at: '2026-11-16T10:00:00Z',
  anteprima_url: `/api/v1/diari/7/allegati/${id}/anteprima`,
  miniatura_url: `/api/v1/diari/7/allegati/${id}/anteprima?lato=320`,
  download_url: `/api/v1/diari/7/allegati/${id}/file`,
})

const json = (stato: number, corpo: unknown) =>
  new Response(corpo === null ? null : JSON.stringify(corpo), { status: stato, headers: { 'Content-Type': 'application/json' } })

const fetchMock = vi.fn<typeof fetch>()
let scope: EffectScope

function crea(invia: InviaFoto, maxMb = 20) {
  scope = effectScope()
  return scope.run(() => useGalleriaFoto(7, 'impresa_1', { invia, maxMb, tipi: ['image/jpeg', 'image/png'] }))!
}

const file = (nome: string, tipo = 'image/jpeg', byte = 10) => new File([new Uint8Array(byte)], nome, { type: tipo })
const attendi = () => new Promise((r) => setTimeout(r, 0))

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  URL.createObjectURL = vi.fn(() => 'blob:anteprima')
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => {
  scope?.stop()
  vi.unstubAllGlobals()
})

describe('galleria foto', () => {
  it('carica l’elenco del modulo', async () => {
    fetchMock.mockResolvedValueOnce(json(200, [allegato(1)]))
    const g = crea(vi.fn())
    await g.carica()
    expect(String(fetchMock.mock.calls[0]![0])).toBe('/api/v1/diari/7/allegati?modulo=impresa_1')
    expect(g.foto.value.map((a) => a.id)).toEqual([1])
  })

  it('invia una foto alla volta con avanzamento; errori per file; riprova con la stessa chiave', async () => {
    let n = 10
    const chiavi: string[] = []
    const invia = vi.fn<InviaFoto>(async (invio, opzioni) => {
      chiavi.push(invio.chiave)
      expect(invio.modulo).toBe('impresa_1')
      opzioni?.avanzamento?.(0.5)
      if (invio.nome === 'rete.jpg' && chiavi.filter((c) => c === invio.chiave).length === 1) {
        throw Object.assign(new Error('Sei offline o il server non risponde.'), {})
      }
      return allegato(++n, invio.nome)
    })
    const g = crea(invia, 2)
    g.aggiungi([file('a.jpg'), file('rete.jpg'), file('grande.jpg', 'image/jpeg', 3 * 1024 * 1024), file('doc.pdf', 'application/pdf')])
    expect(g.invii.value).toHaveLength(4)
    for (let i = 0; i < 10; i++) await attendi()

    expect(invia).toHaveBeenCalledTimes(2) // i file non validi non partono
    expect(g.foto.value.map((a) => a.nome)).toEqual(['a.jpg'])
    const restanti = g.invii.value.map((v) => [v.nome, v.stato, v.definitivo])
    expect(restanti).toEqual([
      ['rete.jpg', 'errore', false],
      ['grande.jpg', 'errore', true],
      ['doc.pdf', 'errore', true],
    ])
    expect(g.invii.value[1]!.errore).toBe("Supera il limite di 2 MB.")
    expect(g.invii.value[2]!.errore).toMatch(/Tipo non consentito/)

    g.riprova(g.invii.value[0]!.id)
    for (let i = 0; i < 10; i++) await attendi()
    expect(chiavi[1]).toBe(chiavi[2]) // stessa foto, stessa Idempotency-Key
    expect(g.foto.value.map((a) => a.nome)).toEqual(['a.jpg', 'rete.jpg'])
    expect(g.invii.value.map((v) => v.nome)).toEqual(['grande.jpg', 'doc.pdf'])

    g.togli(g.invii.value[0]!.id)
    expect(g.invii.value.map((v) => v.nome)).toEqual(['doc.pdf'])
    expect(URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('elimina con conferma; 404 vale come già eliminata', async () => {
    const g = crea(vi.fn())
    g.foto.value = [allegato(1), allegato(2)]
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    expect(await g.elimina(g.foto.value[0]!)).toBe(true)
    expect(fetchMock.mock.calls[0]![1]?.method).toBe('DELETE')
    expect(String(fetchMock.mock.calls[0]![0])).toBe('/api/v1/diari/7/allegati/1')
    fetchMock.mockResolvedValueOnce(json(404, { detail: 'Non trovato.' }))
    expect(await g.elimina(g.foto.value[0]!)).toBe(true)
    expect(g.foto.value).toEqual([])
  })

  it('formatta le dimensioni', () => {
    expect(formattaDimensione(500)).toBe('500 B')
    expect(formattaDimensione(2048)).toBe('2 KB')
    expect(formattaDimensione(1.5 * 1024 * 1024)).toBe('1,5 MB')
  })
})
