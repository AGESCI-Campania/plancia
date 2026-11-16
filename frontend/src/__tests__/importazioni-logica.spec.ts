import { describe, expect, it } from 'vitest'

import {
  campiValorizzati,
  chiedeEdizione,
  estensioneValida,
  ordinaTracciati,
  righeScartate,
  tipoAvvisoRiprova,
  validaLancio,
  type Tracciato,
} from '@/components/importazioni/importazioni'

const t = (chiave: string, estensione = '.csv', edizione_obbligatoria = false): Tracciato => ({
  chiave,
  etichetta: chiave,
  estensione,
  edizione_obbligatoria,
})

const file = (nome: string) => new File(['x'], nome)

describe('validaLancio', () => {
  it('chiede il file', () => {
    expect(validaLancio(t('coca'), null, '')).toEqual({ file: ["Seleziona un file prima di avviare l'import."] })
  })

  it("controlla l'estensione senza badare alle maiuscole", () => {
    expect(validaLancio(t('coca'), file('capi.CSV'), '')).toEqual({})
    expect(validaLancio(t('coca'), file('capi.xlsx'), '').file).toEqual(['Il file deve essere in formato .csv.'])
    expect(validaLancio(t('risposte_eg', '.xlsx'), file('r.csv'), '').file).toEqual([
      'Il file deve essere in formato .xlsx.',
    ])
  })

  it("richiede l'edizione solo se obbligatoria", () => {
    const sq = t('squadriglie', '.csv', true)
    expect(validaLancio(sq, file('sq.csv'), '').edizione_pk).toHaveLength(1)
    expect(validaLancio(sq, file('sq.csv'), '3')).toEqual({})
    expect(validaLancio(t('risposte_eg', '.xlsx'), file('r.xlsx'), '')).toEqual({})
  })
})

describe('tracciati', () => {
  it('ordine consigliato: capi, squadriglie, ragazzi, risposte, poi gli sconosciuti', () => {
    const ordinati = ordinaTracciati([t('nuovo'), t('ragazzi'), t('risposte_eg'), t('squadriglie'), t('coca')])
    expect(ordinati.map((x) => x.chiave)).toEqual(['coca', 'squadriglie', 'ragazzi', 'risposte_eg', 'nuovo'])
  })

  it("chiede l'edizione per squadriglie (obbligatoria) e risposte EG (facoltativa)", () => {
    expect(chiedeEdizione(t('squadriglie', '.csv', true))).toBe(true)
    expect(chiedeEdizione(t('risposte_eg', '.xlsx'))).toBe(true)
    expect(chiedeEdizione(t('coca'))).toBe(false)
  })

  it('estensioneValida', () => {
    expect(estensioneValida('a.b.csv', '.csv')).toBe(true)
    expect(estensioneValida('csv', '.csv')).toBe(false)
  })
})

describe('righe del log', () => {
  it('mostra solo i campi valorizzati', () => {
    expect(campiValorizzati({ nome: 'Ada', email: '', note: null, eta: 0, spazi: '  ' })).toEqual([
      ['nome', 'Ada'],
      ['eta', '0'],
    ])
  })

  it('tipo di avviso dopo "Riprova anomalie"', () => {
    expect(tipoAvvisoRiprova(2, 1)).toBe('success')
    expect(tipoAvvisoRiprova(0, 3)).toBe('warning')
    expect(tipoAvvisoRiprova(0, 0)).toBe('info')
  })

  it('singolare e plurale degli scarti', () => {
    expect(righeScartate(1)).toBe('1 riga scartata')
    expect(righeScartate(4)).toBe('4 righe scartate')
  })
})
