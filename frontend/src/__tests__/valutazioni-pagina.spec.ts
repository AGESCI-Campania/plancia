import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { ErroreApi } from '@/api/http'
import ValutazioneView from '@/views/valutazioni/ValutazioneView.vue'

const get = vi.fn()
vi.mock('@/api/http', async (originale) => {
  const vero = await originale<typeof import('@/api/http')>()
  return { ...vero, api: { get: (...a: unknown[]) => get(...a), post: vi.fn() } }
})

const AZIONI_NESSUNA = {
  puo_valutare_direttamente: false,
  puo_proporre: false,
  puo_confermare: false,
  puo_rigettare: false,
  puo_modificare: false,
  puo_pubblicare: false,
  puo_assegnare_pgv: false,
}

async function monta() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: { template: '<div />' } }] })
  const w = mount(ValutazioneView, { props: { id: 7 }, global: { plugins: [router] } })
  await flushPromises()
  return w
}

describe('pagina valutazione', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
  })

  it('senza valutazione chiede le azioni e propone la valutazione diretta', async () => {
    get.mockImplementation((url: string) => {
      if (url === '/diari/7/valutazione') return Promise.reject(new ErroreApi(404, 'Nessuna valutazione'))
      if (url === '/diari/7/valutazione/azioni')
        return Promise.resolve({ ...AZIONI_NESSUNA, puo_valutare_direttamente: true, puo_assegnare_pgv: true })
      return Promise.resolve({ squadriglia: 'Tigri', reparto: 'Orione', edizione_anno: 2026, stato: 'inviato', stato_display: 'Inviato' })
    })
    const w = await monta()
    expect(get).toHaveBeenCalledWith('/diari/7/valutazione/azioni')
    expect(w.text()).toContain('Valuta direttamente')
    expect(w.text()).toContain('Assegnazioni Pattuglia GV')
    expect(w.text()).not.toContain('Pubblica esito')
  })

  it('a chi non può vederla mostra solo il messaggio dell’API', async () => {
    get.mockRejectedValue(new ErroreApi(403, 'Valutazione non ancora pubblicata.'))
    const w = await monta()
    expect(w.text()).toContain('Valutazione non ancora pubblicata.')
    expect(w.text()).not.toContain('Esito')
    expect(w.find('form').exists()).toBe(false)
  })

  it('proposta in revisione: conferma e rigetto per chi può confermare', async () => {
    get.mockImplementation((url: string) =>
      url === '/diari/7/valutazione'
        ? Promise.resolve({
            esito: null, esito_display: null, stato: 'in_revisione', stato_display: 'In revisione', note: '',
            pubblicata: false, assegnazioni: [], proposta_esito: 'approvata', proposta_esito_display: 'Approvata',
            azioni: { ...AZIONI_NESSUNA, puo_confermare: true, puo_rigettare: true },
          })
        : Promise.resolve(null),
    )
    const w = await monta()
    expect(w.text()).toContain('in attesa di conferma')
    expect(w.text()).toContain('Conferma proposta')
    expect(w.text()).toContain('Rigetta proposta')
  })
})
