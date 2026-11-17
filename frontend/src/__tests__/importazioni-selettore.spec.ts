import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ImportazioniSelettoreSocio from '@/components/importazioni/ImportazioniSelettoreSocio.vue'

const soci = [
  { id: 1, user_pk: null, codice_socio: '111', categoria: 'capo', nome: 'Ada', cognome: 'Rossi', gruppo: 'G1', zona: 'Z', label: 'Rossi Ada (111)' },
  { id: 2, user_pk: null, codice_socio: '222', categoria: 'capo', nome: 'Bruno', cognome: 'Verdi', gruppo: 'G2', zona: 'Z', label: 'Verdi Bruno (222)' },
]

describe('ImportazioniSelettoreSocio', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers()
    fetchMock = vi.fn(async () => new Response(JSON.stringify(soci), { headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  async function digita(w: ReturnType<typeof mount>, testo: string) {
    const input = w.find('input')
    await input.setValue(testo)
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
  }

  it('cerca solo da 2 caratteri, con la categoria, dopo una pausa', async () => {
    const w = mount(ImportazioniSelettoreSocio, { props: { etichetta: 'Capo Reparto', categoria: 'capo' } })
    await digita(w, 'R')
    expect(fetchMock).not.toHaveBeenCalled()
    await digita(w, 'Ro')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = String(fetchMock.mock.calls[0]![0])
    expect(url).toContain('/api/v1/org/soci?')
    expect(url).toContain('q=Ro')
    expect(url).toContain('categoria=capo')
    expect(w.findAll('[role="option"]')).toHaveLength(2)
    expect(w.find('input').attributes('aria-expanded')).toBe('true')
  })

  it('frecce e Invio scelgono un socio (v-model)', async () => {
    const w = mount(ImportazioniSelettoreSocio, { props: { etichetta: 'Capo Reparto' } })
    await digita(w, 'Ve')
    const input = w.find('input')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toMatch(/opz-1$/)
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual([soci[1]])
    expect((input.element as HTMLInputElement).value).toBe('Verdi Bruno (222)')
    expect(input.attributes('aria-expanded')).toBe('false')
  })

  it('cambiare il testo dopo la scelta azzera la selezione', async () => {
    const w = mount(ImportazioniSelettoreSocio, { props: { etichetta: 'Capo Reparto', modelValue: soci[0] } })
    await digita(w, 'Rossi')
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual([null])
  })

  it('nessun risultato', async () => {
    fetchMock.mockImplementation(async () => new Response('[]', { headers: { 'Content-Type': 'application/json' } }))
    const w = mount(ImportazioniSelettoreSocio, { props: { etichetta: 'Capo Reparto' } })
    await digita(w, 'zzz')
    expect(w.text()).toContain('Nessun socio trovato.')
  })
})
