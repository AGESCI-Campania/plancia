import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ImportazioniSchedaTracciato from '@/components/importazioni/ImportazioniSchedaTracciato.vue'
import { useAvvisiStore } from '@/stores/avvisi'

const squadriglie = { chiave: 'squadriglie', etichetta: 'Squadriglie iscritte', estensione: '.csv', edizione_obbligatoria: true }
const edizioni = [{ id: 7, anno: 2026, stato: 'aperta', stato_display: 'Aperta' }]

function json(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })
}

async function scegliFile(w: ReturnType<typeof mount>, nome: string): Promise<void> {
  const input = w.find('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: [new File(['a;b'], nome)], configurable: true })
  await input.trigger('change')
}

describe('ImportazioniSchedaTracciato', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    setActivePinia(createPinia())
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  it("non invia con l'estensione sbagliata o senza edizione obbligatoria", async () => {
    const w = mount(ImportazioniSchedaTracciato, { props: { tracciato: squadriglie, numero: 2, edizioni } })
    await scegliFile(w, 'sq.xlsx')
    expect(w.text()).toContain('Il file deve essere in formato .csv.')
    await scegliFile(w, 'sq.csv')
    await w.find('form').trigger('submit')
    expect(w.text()).toContain("Seleziona un'edizione per l'import squadriglie iscritte.")
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('202: multipart con file ed edizione, avviso e evento', async () => {
    fetchMock.mockResolvedValue(json({ tracciato: 'squadriglie', task_id: 'x', messaggio: 'Import avviato.' }, 202))
    const w = mount(ImportazioniSchedaTracciato, { props: { tracciato: squadriglie, numero: 2, edizioni } })
    await scegliFile(w, 'sq.csv')
    await w.find('select').setValue('7')
    await w.find('form').trigger('submit')
    await flushPromises()
    const [url, opzioni] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/v1/importazioni/lancia/squadriglie')
    const corpo = (opzioni as RequestInit).body as FormData
    expect((corpo.get('file') as File).name).toBe('sq.csv')
    expect(corpo.get('edizione_pk')).toBe('7')
    expect(w.emitted('avviato')).toHaveLength(1)
    expect(useAvvisiStore().avvisi.at(-1)?.testo).toBe('Import avviato.')
  })

  it('422: errori per campo dal backend', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'Dati non validi.', errori: { edizione_pk: ['Edizione inesistente.'] } }, 422))
    const w = mount(ImportazioniSchedaTracciato, { props: { tracciato: squadriglie, numero: 2, edizioni } })
    await scegliFile(w, 'sq.csv')
    await w.find('select').setValue('7')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.text()).toContain('Edizione inesistente.')
    expect(w.emitted('avviato')).toBeUndefined()
  })
})
