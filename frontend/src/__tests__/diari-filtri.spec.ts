import { describe, expect, it } from 'vitest'

import {
  filtriAttivi,
  filtriDaQuery,
  filtriVuoti,
  formattaData,
  nomeReferente,
  parametriApi,
  prossimoOrdinamento,
  queryDaFiltri,
  versoOrdinamento,
  vociModuli,
  type DiarioDettaglio,
} from '@/components/diari/diari'

describe('filtri dell’elenco diari', () => {
  it('legge la query string e ignora i valori non validi', () => {
    const f = filtriDaQuery({
      edizione: '3',
      zona: 'abc',
      gruppo: '-2',
      reparto: ['7', '8'],
      stato: 'inviato, approvato,,',
      tipo: 'nuovo',
      q: '  rossi ',
      ordina: '-squadriglia',
      pagina: '0',
      per_pagina: '33',
    })
    expect(f).toEqual({
      ...filtriVuoti(),
      edizione: 3,
      reparto: 7,
      stati: ['inviato', 'approvato'],
      tipo: 'nuovo',
      q: 'rossi',
      ordina: '-squadriglia',
    })
  })

  it('andata e ritorno tra filtri e query string', () => {
    const f = {
      ...filtriVuoti(),
      zona: 2,
      stati: ['in_compilazione', 'inviato'],
      specialita: 'Natura',
      pagina: 3,
      perPagina: 50,
    }
    const query = queryDaFiltri(f)
    expect(query).toEqual({
      zona: '2',
      stato: 'in_compilazione,inviato',
      specialita: 'Natura',
      pagina: '3',
      per_pagina: '50',
    })
    expect(filtriDaQuery(query as Record<string, string>)).toEqual(f)
  })

  it('la query string dei filtri predefiniti è vuota', () => {
    expect(queryDaFiltri(filtriVuoti())).toEqual({})
  })

  it('traduce i filtri nei parametri dell’API con limit e offset', () => {
    const p = parametriApi({
      ...filtriVuoti(),
      edizione: 1,
      stati: ['inviato'],
      q: ' x ',
      pagina: 3,
      perPagina: 10,
    })
    expect(p).toEqual({
      edizione_id: 1,
      zona_id: undefined,
      gruppo_id: undefined,
      reparto_id: undefined,
      stato: 'inviato',
      tipo: undefined,
      specialita: undefined,
      q: 'x',
      ordina: undefined,
      limit: 10,
      offset: 20,
    })
  })

  it('riconosce i filtri attivi (non l’ordinamento né la pagina)', () => {
    expect(filtriAttivi({ ...filtriVuoti(), ordina: 'stato', pagina: 4 })).toBe(false)
    expect(filtriAttivi({ ...filtriVuoti(), stati: ['inviato'] })).toBe(true)
    expect(filtriAttivi({ ...filtriVuoti(), q: '   ' })).toBe(false)
  })

  it('alterna l’ordinamento di una colonna', () => {
    expect(prossimoOrdinamento('', 'stato')).toBe('stato')
    expect(prossimoOrdinamento('stato', 'stato')).toBe('-stato')
    expect(prossimoOrdinamento('-stato', 'stato')).toBe('stato')
    expect(prossimoOrdinamento('-stato', 'tipo')).toBe('tipo')
    expect(versoOrdinamento('-stato', 'stato')).toBe('descending')
    expect(versoOrdinamento('stato', 'stato')).toBe('ascending')
    expect(versoOrdinamento('tipo', 'stato')).toBe('none')
  })
})

describe('presentazione', () => {
  it('formatta date e referenti', () => {
    expect(formattaData('2026-03-09')).toBe('09/03/2026')
    expect(formattaData('2026-03-09T10:00:00Z')).toBe('09/03/2026')
    expect(formattaData(null)).toBe('')
    expect(nomeReferente({ id: 1, nome: 'Mario', cognome: 'Rossi' })).toBe('Rossi Mario')
    expect(nomeReferente(null)).toBe('')
  })
})

function dettaglio(
  stato: string,
  moduli: Partial<NonNullable<DiarioDettaglio['stato_moduli']>>,
): DiarioDettaglio {
  return {
    id: 5,
    stato,
    stato_moduli: {
      anagrafica: true,
      presentazione: false,
      impresa_1: true,
      impresa_2: false,
      missione: false,
      impresa_2_obbligatoria: true,
      missione_obbligatoria: true,
      moduli_csq_completi: false,
      relazione_finale: null,
      versioni: {},
      ...moduli,
    },
  } as unknown as DiarioDettaglio
}

describe('vociModuli', () => {
  it('senza relazione visibile (Capo Squadriglia) mostra solo i moduli 1–5', () => {
    const voci = vociModuli(dettaglio('in_compilazione', {}))
    expect(voci.map((v) => v.numero)).toEqual([1, 2, 3, 4, 5])
    expect(voci.map((v) => v.compilato)).toEqual([true, false, true, false, false])
    expect(voci[2]!.to).toBe('/diari/5/imprese/1')
  })

  it('rinnovo: 2ª impresa e missione facoltative', () => {
    const voci = vociModuli(
      dettaglio('in_compilazione', { impresa_2_obbligatoria: false, missione_obbligatoria: false }),
    )
    expect(voci.filter((v) => v.facoltativo).map((v) => v.chiave)).toEqual([
      'impresa_2',
      'missione',
    ])
  })

  it('relazione finale: non disponibile prima dell’invio del Capo Squadriglia', () => {
    const prima = vociModuli(dettaglio('in_compilazione', { relazione_finale: false }))
    expect(prima[5]).toMatchObject({
      numero: 6,
      nonDisponibile: true,
      to: '/diari/5/relazione-finale',
    })
    const dopo = vociModuli(dettaglio('relazione_finale', { relazione_finale: false }))
    expect(dopo[5]!.nonDisponibile).toBe(false)
  })
})
