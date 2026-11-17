import { describe, expect, it } from 'vitest'

import { ordinaRighe } from '@/components/inviti/ordinamento'
import {
  badgeConsegna,
  coloreRuolo,
  coloreStatoTicket,
  data,
  dataOra,
  descriviBrowser,
  messaggioErrore,
  offsetQuery,
  testoQuery,
} from '@/components/utenti/formato'
import type { RigaInviti } from '@/components/utenti/tipi'

describe('date', () => {
  it('formatta in italiano e gestisce i valori mancanti', () => {
    expect(data('2026-11-16T10:05:00')).toBe('16/11/2026')
    expect(dataOra('2026-11-16T10:05:00')).toMatch(/^16\/11\/2026,? 10:05$/)
    expect(data(null)).toBe('—')
    expect(dataOra('non-una-data')).toBe('—')
  })
})

describe('colori dei badge', () => {
  it('ruoli e stati dei ticket noti, secondario per gli altri', () => {
    expect(coloreRuolo('admin')).toBe('danger')
    expect(coloreRuolo('csq')).toBe('success')
    expect(coloreRuolo('sconosciuto')).toBe('secondary')
    expect(coloreStatoTicket('in_lavorazione')).toBe('warning')
    expect(coloreStatoTicket('chiuso')).toBe('success')
  })

  it('stato di consegna: solo quelli da segnalare', () => {
    expect(badgeConsegna('bounce')?.colore).toBe('danger')
    expect(badgeConsegna('consegnato')?.testo).toBe('Consegnato')
    expect(badgeConsegna('in_attesa')).toBeNull()
    expect(badgeConsegna('inviato')).toBeNull()
  })
})

describe('descriviBrowser', () => {
  it('riconosce browser e sistema principali', () => {
    expect(
      descriviBrowser(
        'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
      ),
    ).toBe('Safari su iPhone')
    expect(
      descriviBrowser(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 Edg/130.0',
      ),
    ).toBe('Edge su Windows')
    expect(descriviBrowser('Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0')).toBe('Firefox su Linux')
    expect(descriviBrowser('')).toBe('Dispositivo sconosciuto')
  })
})

describe('messaggioErrore', () => {
  it('mostra gli errori non di campo e dei campi assenti dal form', () => {
    expect(messaggioErrore('Dati non validi.', { __all__: ['Non puoi.'] }, ['ruolo'])).toBe('Non puoi.')
    expect(messaggioErrore('Dati non validi.', { backend: ['Canale non valido.'] }, ['tipo'])).toBe('Canale non valido.')
  })

  it('tace se gli errori sono tutti sui campi mostrati, altrimenti usa il messaggio', () => {
    expect(messaggioErrore('Dati non validi.', { ruolo: ['Obbligatorio.'] }, ['ruolo'])).toBe('')
    expect(messaggioErrore('Permesso negato.', {})).toBe('Permesso negato.')
  })
})

describe('parametri di query', () => {
  it('stringhe e offset validi', () => {
    expect(testoQuery('abc')).toBe('abc')
    expect(testoQuery(['x', 'y'])).toBe('x')
    expect(testoQuery(undefined)).toBe('')
    expect(offsetQuery('50')).toBe(50)
    expect(offsetQuery('-3')).toBe(0)
    expect(offsetQuery('abc')).toBe(0)
  })
})

describe('ordinaRighe', () => {
  const riga = (squadriglia: string, csq: string | null): RigaInviti => ({
    diario_id: squadriglia.length,
    squadriglia,
    reparto: 'R',
    gruppo: 'G',
    zona: 'Z',
    csq: csq ? { socio_id: 1, nome: '', cognome: csq, provvisorio: false } : null,
    crp: null,
    ultimo_invito_csq: null,
    ultimo_invito_crp: null,
    inviti_reinviabili: [],
  })
  const righe = [riga('Volpi', 'Rossi'), riga('aquile', null), riga('Èlfi', 'bianchi')]

  it('alfabetico italiano senza distinguere maiuscole e accenti', () => {
    expect(ordinaRighe(righe, 'squadriglia').map((r) => r.squadriglia)).toEqual(['aquile', 'Èlfi', 'Volpi'])
    expect(ordinaRighe(righe, 'squadriglia', false).map((r) => r.squadriglia)).toEqual(['Volpi', 'Èlfi', 'aquile'])
  })

  it('i vuoti in fondo e l’originale non cambia', () => {
    expect(ordinaRighe(righe, 'csq').map((r) => r.squadriglia)).toEqual(['Èlfi', 'Volpi', 'aquile'])
    expect(righe[0]!.squadriglia).toBe('Volpi')
  })
})
