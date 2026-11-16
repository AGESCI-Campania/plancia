import { describe, expect, it } from 'vitest'

import type { Edizione } from '@/api/tipi-edizioni'
import {
  anteprimaCartella,
  azioneSuccessiva,
  coloreEsito,
  corpoEdizione,
  direzioneOrdinamento,
  ESITI_PROPOSTA,
  formatoData,
  formDaEdizione,
  messaggioAccessoValutazione,
  ordinamentoSuccessivo,
  periodoEvento,
  validaEdizione,
} from '@/composables/edizioni'

const edizione: Edizione = {
  id: 3,
  anno: 2026,
  stato: 'aperta',
  stato_display: 'Aperta',
  scadenza_evento: '2026-03-01',
  scadenza_assemblea: null,
  data_evento_inizio: '2026-05-10',
  data_evento_fine: '2026-05-12',
  evento_comune: 'Salerno',
  evento_localita: '',
}

describe('date', () => {
  it('formatta le date ISO in italiano', () => {
    expect(formatoData('2026-03-01')).toBe('01/03/2026')
    expect(formatoData('2026-03-01T10:00:00Z')).toBe('01/03/2026')
    expect(formatoData(null)).toBe('')
  })

  it("compone il periodo dell'evento", () => {
    expect(periodoEvento(edizione)).toBe('10/05/2026 – 12/05/2026')
    expect(periodoEvento({ data_evento_inizio: '2026-05-10', data_evento_fine: null })).toBe('10/05/2026')
    expect(periodoEvento({ data_evento_inizio: null, data_evento_fine: null })).toBe('')
  })
})

describe('FSM edizione', () => {
  it('propone il passo successivo per ogni stato', () => {
    expect(azioneSuccessiva('bozza')?.azione).toBe('apri')
    expect(azioneSuccessiva('aperta')?.azione).toBe('avvia-valutazione')
    expect(azioneSuccessiva('in_valutazione')?.azione).toBe('chiudi')
    expect(azioneSuccessiva('chiusa')).toBeNull()
  })
})

describe('form edizione', () => {
  it('converte da e verso il corpo dell’API', () => {
    const f = formDaEdizione(edizione)
    expect(f.anno).toBe('2026')
    expect(f.scadenza_assemblea).toBe('')
    const corpo = corpoEdizione({ ...f, evento_localita: '  Base scout ' })
    expect(corpo.anno).toBe(2026)
    expect(corpo.scadenza_assemblea).toBeNull()
    expect(corpo.evento_localita).toBe('Base scout')
  })

  it('una nuova edizione parte in bozza con l’anno corrente', () => {
    const f = formDaEdizione(null)
    expect(f.stato).toBe('bozza')
    expect(f.anno).toBe(String(new Date().getFullYear()))
  })

  it('valida anno e date dell’evento', () => {
    const f = formDaEdizione(edizione)
    expect(validaEdizione(f)).toEqual({})
    expect(validaEdizione({ ...f, anno: '26' }).anno).toBeDefined()
    expect(validaEdizione({ ...f, data_evento_fine: '2026-05-01' }).data_evento_fine).toBeDefined()
  })
})

describe('Drive', () => {
  it("costruisce l'anteprima del nome cartella", () => {
    expect(anteprimaCartella('{edizione}_{id_univoco} {nome_squadriglia}', 2026)).toBe('2026_00001_Aquile')
    expect(anteprimaCartella(' {nome_zona}/{specialita} ', 2026)).toBe('Salerno_Campismo')
  })
})

describe('ordinamento tabella', () => {
  it('alterna crescente e decrescente sulla stessa colonna', () => {
    expect(ordinamentoSuccessivo('', 'stato')).toBe('stato')
    expect(ordinamentoSuccessivo('stato', 'stato')).toBe('-stato')
    expect(ordinamentoSuccessivo('-stato', 'stato')).toBe('stato')
    expect(ordinamentoSuccessivo('-stato', 'crp')).toBe('crp')
    expect(direzioneOrdinamento('-stato', 'stato')).toBe('descending')
    expect(direzioneOrdinamento('stato', 'crp')).toBe('none')
  })
})

describe('valutazione', () => {
  it('la Pattuglia GV propone solo Approvata o Non approvata', () => {
    expect(ESITI_PROPOSTA.map((e) => e.valore)).toEqual(['approvata', 'non_approvata'])
  })

  it('colori e messaggi', () => {
    expect(coloreEsito('approvata')).toBe('success')
    expect(coloreEsito('maggiori_info')).toBe('warning')
    expect(coloreEsito(null)).toBe('secondary')
    expect(messaggioAccessoValutazione(403, 'Valutazione non ancora pubblicata.')).toBe(
      'Valutazione non ancora pubblicata.',
    )
    expect(messaggioAccessoValutazione(404, 'x')).toBe('Diario non trovato.')
  })
})
