import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import StatisticheGraficoBarre from '@/components/statistiche/StatisticheGraficoBarre.vue'
import {
  descriviRiga,
  massimo,
  percentuale,
  rigaPubblicazione,
  rigaStatoTicket,
  righeZone,
  segmenti,
  SERIE_ESITI,
  type StatZona,
} from '@/components/statistiche/grafici'

const zona = (nome: string, totale: number, approvati: number, non_approvati: number, maggiori_info = 0): StatZona => ({
  zona: { id: nome.length, nome },
  totale,
  approvati,
  non_approvati,
  maggiori_info,
  pubblicati: approvati + non_approvati,
  percentuale_approvati: percentuale(approvati, totale),
})

describe('trasformazioni per i grafici', () => {
  it('righeZone: il resto dei diari è "in corso", mai negativo', () => {
    const [a, b] = righeZone([zona('A', 10, 4, 2, 1), zona('B', 2, 2, 1)])
    expect(a!.valori).toEqual({ approvati: 4, non_approvati: 2, maggiori_info: 1, altri: 3 })
    expect(b!.valori.altri).toBe(0)
  })

  it('segmenti in proporzione alla riga più lunga, senza quelli a zero', () => {
    const righe = righeZone([zona('A', 10, 5, 0), zona('B', 5, 5, 0)])
    const max = massimo(righe, SERIE_ESITI)
    expect(max).toBe(10)
    const sB = segmenti(righe[1]!, SERIE_ESITI, max)
    expect(sB.map((s) => [s.chiave, s.larghezza])).toEqual([['approvati', 50]])
    expect(segmenti(righe[0]!, SERIE_ESITI, 0).every((s) => s.larghezza === 0)).toBe(true)
  })

  it('pubblicazione e stato dei ticket', () => {
    const g = { totale: 10, inviati: 6, approvati: 3, non_approvati: 1, in_compilazione: 2, pubblicati: 4 }
    expect(rigaPubblicazione(g).valori).toEqual({ approvati: 3, non_approvati: 1, non_pubblicati: 6 })
    expect(rigaStatoTicket({ totale: 5, aperti: 2, chiusi: 1, per_categoria: [] }).valori).toEqual({
      aperti: 2,
      chiusi: 1,
      altri: 2,
    })
  })

  it('percentuale e descrizione testuale', () => {
    expect(percentuale(1, 3)).toBe(33)
    expect(percentuale(1, 0)).toBe(0)
    const [r] = righeZone([zona('Nord', 3, 2, 1)])
    expect(descriviRiga(r!, SERIE_ESITI)).toBe('Nord: 2 approvati, 1 non approvati (totale 3)')
  })
})

describe('StatisticheGraficoBarre', () => {
  it('barre nascoste agli screen reader e tabella dati come alternativa', () => {
    const w = mount(StatisticheGraficoBarre, {
      props: { titolo: 'Esiti per zona', etichettaRiga: 'Zona', serie: SERIE_ESITI, righe: righeZone([zona('Sud', 4, 1, 1)]) },
    })
    expect(w.find('figcaption').text()).toBe('Esiti per zona')
    expect(w.find('.plancia-grafico__righe').attributes('aria-hidden')).toBe('true')
    const celle = w.findAll('tbody tr td').map((c) => c.text())
    expect(w.find('tbody th').text()).toBe('Sud')
    expect(celle).toEqual(['1', '1', '0', '2', '4'])
    expect(w.findAll('.plancia-grafico__segmento')).toHaveLength(3)
  })
})
