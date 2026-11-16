import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import UtentiSelettoreSocio from '@/components/utenti/UtentiSelettoreSocio.vue'
import type { SocioAutocomplete } from '@/components/utenti/tipi'

const socio: SocioAutocomplete = {
  id: 7,
  user_pk: null,
  codice_socio: '123456',
  categoria: 'capo',
  nome: 'Mario',
  cognome: 'Rossi',
  gruppo: 'Napoli 1',
  zona: 'Partenope',
  label: 'Rossi Mario (123456)',
}

describe('UtentiSelettoreSocio', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers()
    fetchMock = vi.fn(async () => new Response(JSON.stringify([socio]), { headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('cerca dopo 2 caratteri con la categoria e sceglie con la tastiera', async () => {
    const w = mount(UtentiSelettoreSocio, { props: { categoria: 'capo', modelValue: null } })
    const input = w.get('input[role="combobox"]')

    await input.setValue('r')
    vi.advanceTimersByTime(300)
    expect(fetchMock).not.toHaveBeenCalled()
    expect(w.text()).toContain('almeno 2 caratteri')

    await input.setValue('ro')
    vi.advanceTimersByTime(300)
    await flushPromises()
    const url = String(fetchMock.mock.calls[0]![0])
    expect(url).toContain('/api/v1/org/soci?')
    expect(url).toContain('q=ro')
    expect(url).toContain('categoria=capo')
    expect(input.attributes('aria-expanded')).toBe('true')
    expect(w.findAll('[role="option"]')).toHaveLength(1)

    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual([socio])
    expect(input.attributes('aria-expanded')).toBe('false')
  })

  it('scrivere di nuovo toglie la scelta', async () => {
    const w = mount(UtentiSelettoreSocio, { props: { modelValue: socio } })
    const input = w.get('input[role="combobox"]')
    expect((input.element as HTMLInputElement).value).toBe(socio.label)
    await input.setValue('Bi')
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual([null])
  })
})
