import { describe, expect, it } from 'vitest'

import { ErroreApi } from '@/api/http'
import { erroreDiRiavvio, faseDa, righeLog, type StatoAggiornamento } from '@/composables/impostazioni-aggiornamento'
import { dimensioneLeggibile, inserisciInTesto, richiedeSorgente, segnaposto, sposta } from '@/composables/impostazioni-editor'
import { markdownSicuro } from '@/composables/impostazioni-markdown'
import { tipoRiautenticazione } from '@/composables/riautenticazione'

describe('markdownSicuro', () => {
  it('converte titoli, elenchi, enfasi, codice e link', () => {
    const html = markdownSicuro('## Novità\n\n- **Nuovo** editor\n- _corsivo_ e `codice`\n\nVedi [qui](https://example.org).')
    expect(html).toContain('<h4>Novità</h4>')
    expect(html).toContain('<ul>\n<li><strong>Nuovo</strong> editor</li>')
    expect(html).toContain('<em>corsivo</em> e <code>codice</code>')
    expect(html).toContain('<a href="https://example.org" target="_blank" rel="noopener noreferrer">qui</a>')
  })

  it("non lascia passare HTML arbitrario né link non http", () => {
    const html = markdownSicuro('<script>alert(1)</script> <img src=x onerror=alert(1)>\n\n[x](javascript:alert(1))')
    expect(html).not.toMatch(/<script|<img|href="javascript/)
    expect(html).toContain('&lt;script&gt;')
  })

  it('elenchi numerati e paragrafi su più righe', () => {
    expect(markdownSicuro('1. uno\n2. due')).toBe('<ol>\n<li>uno</li>\n<li>due</li>\n</ol>')
    expect(markdownSicuro('riga uno\nriga due')).toBe('<p>riga uno riga due</p>')
    expect(markdownSicuro('')).toBe('')
  })
})

describe('richiedeSorgente', () => {
  it("accetta l'HTML semplice dell'editor visuale", () => {
    expect(richiedeSorgente('<h2>Ciao</h2><p><strong>{{ nome }}</strong> <a href="https://x.it">link</a></p><ul><li>a</li></ul>')).toBe(false)
    expect(richiedeSorgente('<p><img src="/media/a.png" alt="a" width="200"></p>')).toBe(false)
    expect(richiedeSorgente('')).toBe(false)
  })

  it('riconosce tabelle, stili, documenti completi e istruzioni di template', () => {
    expect(richiedeSorgente('<table><tr><td>x</td></tr></table>')).toBe(true)
    expect(richiedeSorgente('<p style="color:red">x</p>')).toBe(true)
    expect(richiedeSorgente('<!DOCTYPE html><html><body>x</body></html>')).toBe(true)
    expect(richiedeSorgente('<p>{% for sq in lista %}{{ sq }}{% endfor %}</p>')).toBe(true)
    expect(richiedeSorgente('<div>x</div>')).toBe(true)
  })
})

describe('utilità di testo e liste', () => {
  it('segnaposto e inserimento al cursore', () => {
    expect(segnaposto('nome')).toBe('{{ nome }}')
    expect(inserisciInTesto('Ciao !', '{{ nome }}', 5)).toEqual({ valore: 'Ciao {{ nome }}!', cursore: 15 })
    expect(inserisciInTesto('abc', 'X', 1, 2)).toEqual({ valore: 'aXc', cursore: 2 })
    expect(inserisciInTesto('abc', 'X', 99)).toEqual({ valore: 'abcX', cursore: 4 })
  })

  it('sposta un elemento entro i limiti', () => {
    expect(sposta([1, 2, 3], 0, 1)).toEqual([2, 1, 3])
    expect(sposta([1, 2, 3], 2, -2)).toEqual([3, 1, 2])
    expect(sposta([1, 2, 3], 0, -1)).toEqual([1, 2, 3])
    expect(sposta([1, 2, 3], 2, 1)).toEqual([1, 2, 3])
  })

  it('dimensioni leggibili', () => {
    expect(dimensioneLeggibile(0)).toBe('—')
    expect(dimensioneLeggibile(512)).toBe('512 byte')
    expect(dimensioneLeggibile(1536)).toBe('1,5 KB')
    expect(dimensioneLeggibile(3 * 1024 * 1024)).toBe('3 MB')
  })
})

function stato(parziale: Partial<StatoAggiornamento> & { esito?: string }): StatoAggiornamento {
  const { esito, ...resto } = parziale
  return {
    installata: '3.0.0',
    richiesta: esito ? ({ stato: esito, log: 'a\nb' } as StatoAggiornamento['richiesta']) : null,
    stato: null,
    in_corso: false,
    ...resto,
  }
}

describe('monitoraggio aggiornamento', () => {
  it('fase dalla richiesta e dalla versione installata', () => {
    expect(faseDa(stato({ esito: 'in_attesa' }), '3.0.0')).toBe('in_corso')
    expect(faseDa(stato({ esito: 'in_corso', in_corso: true }), '3.0.0')).toBe('in_corso')
    expect(faseDa(stato({ esito: 'fallito' }), '3.0.0')).toBe('fallito')
    expect(faseDa(stato({ esito: 'completato', installata: '3.1.0' }), '3.0.0')).toBe('completato')
    // versione cambiata prima che lo storico sia chiuso: i container nuovi sono su
    expect(faseDa(stato({ esito: 'in_corso', installata: '3.1.0' }), '3.0.0')).toBe('completato')
    expect(faseDa(stato({}), '3.0.0')).toBe('inattivo')
  })

  it('durante il riavvio rete assente, 502/503/504 non sono errori', () => {
    expect(erroreDiRiavvio(new ErroreApi(0, 'offline'))).toBe(true)
    expect(erroreDiRiavvio(new ErroreApi(503, 'manutenzione'))).toBe(true)
    expect(erroreDiRiavvio(new ErroreApi(502, 'bad gateway'))).toBe(true)
    expect(erroreDiRiavvio(new ErroreApi(403, 'vietato'))).toBe(false)
    expect(erroreDiRiavvio(new Error('x'))).toBe(false)
  })

  it('righe di log da stato.json o dallo storico', () => {
    expect(righeLog(stato({ stato: { log: ['uno', 'due'] } }))).toEqual(['uno', 'due'])
    expect(righeLog(stato({ esito: 'in_corso' }))).toEqual(['a', 'b'])
    expect(righeLog(null)).toEqual([])
  })
})

describe('tipoRiautenticazione', () => {
  it('sceglie password o codice MFA dai flussi allauth', () => {
    expect(tipoRiautenticazione([{ id: 'reauthenticate' }, { id: 'mfa_reauthenticate' }])).toBe('password')
    expect(tipoRiautenticazione([{ id: 'mfa_reauthenticate' }])).toBe('codice')
    expect(tipoRiautenticazione([])).toBeNull()
    expect(tipoRiautenticazione(undefined)).toBe('password')
  })
})
