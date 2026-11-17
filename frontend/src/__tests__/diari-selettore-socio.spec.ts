import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import DiariSelettoreSocio from '@/components/diari/DiariSelettoreSocio.vue'

const SOCI = [
  {
    id: 1,
    label: 'Rossi Mario (Napoli 1)',
    nome: 'Mario',
    cognome: 'Rossi',
    categoria: 'capo',
    codice_socio: '1',
    gruppo: 'Napoli 1',
    zona: 'Napoli',
  },
  {
    id: 2,
    label: 'Rossi Lucia (Napoli 2)',
    nome: 'Lucia',
    cognome: 'Rossi',
    categoria: 'capo',
    codice_socio: '2',
    gruppo: 'Napoli 2',
    zona: 'Napoli',
  },
]

describe('DiariSelettoreSocio', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers()
    fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify(SOCI), { headers: { 'Content-Type': 'application/json' } }),
    )
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  async function digita(wrapper: ReturnType<typeof mount>, testo: string): Promise<void> {
    await wrapper.get('input').setValue(testo)
    await vi.advanceTimersByTimeAsync(300)
    await flushPromises()
  }

  it('non cerca con meno di 2 caratteri', async () => {
    const w = mount(DiariSelettoreSocio, {
      props: { etichetta: 'Nuovo Capo Reparto', categoria: 'capo' },
    })
    await digita(w, 'r')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('cerca con la categoria, esclude il referente attuale e sceglie da tastiera', async () => {
    const w = mount(DiariSelettoreSocio, {
      props: {
        etichetta: 'Nuovo Capo Reparto',
        categoria: 'capo',
        escludi: [1],
        'onUpdate:modelValue': () => {},
      },
    })
    await digita(w, 'ross')
    const url = String(fetchMock.mock.calls[0]![0])
    expect(url).toContain('/api/v1/org/soci?')
    expect(url).toContain('q=ross')
    expect(url).toContain('categoria=capo')

    const opzioni = w.findAll('[role="option"]')
    expect(opzioni.map((o) => o.text())).toEqual(['Rossi Lucia (Napoli 2)'])
    expect(w.get('input').attributes('aria-expanded')).toBe('true')

    await w.get('input').trigger('keydown', { key: 'Enter' })
    const emessi = w.emitted('update:modelValue') ?? []
    expect(emessi.at(-1)?.[0]).toMatchObject({ id: 2 })
    expect(w.get('input').attributes('aria-expanded')).toBe('false')
  })

  it('mostra "Nessun risultato." se la ricerca non trova nulla', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('[]', { headers: { 'Content-Type': 'application/json' } }),
    )
    const w = mount(DiariSelettoreSocio, {
      props: { etichetta: 'Nuovo Capo Squadriglia', categoria: 'ragazzo' },
    })
    await digita(w, 'zzz')
    expect(w.text()).toContain('Nessun risultato.')
  })
})
