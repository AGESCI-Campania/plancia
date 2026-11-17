import { describe, expect, it } from 'vitest'

import type { Me, Menu } from '@/api/tipi'
import { vociMenu } from '@/layouts/menu'

const nessunFlag: Menu = {
  puo_vedere_diari: false,
  puo_gestire_edizioni: false,
  puo_vedere_utenti: false,
  puo_gestire_inviti: false,
  puo_gestire_inviti_crp: false,
  puo_importare: false,
  puo_vedere_statistiche: false,
  puo_vedere_impostazioni: false,
  puo_vedere_helpdesk: true,
  puo_gestire_helpdesk: false,
  puo_usare_admin_django: false,
}

function utente(ruolo: string, flag: Partial<Menu> = {}): Me {
  return {
    id: 1,
    email: 'x@test.it',
    first_name: '',
    last_name: '',
    nome_completo: 'X',
    ruolo: { chiave: ruolo, etichetta: ruolo },
    ruoli_attivi: [],
    is_staff_plancia: false,
    is_superuser: false,
    mfa_attiva: false,
    mfa_richiesta: false,
    mfa_da_configurare: false,
    puo_modificare_email: false,
    menu: { ...nessunFlag, ...flag },
  }
}

describe('vociMenu', () => {
  it('il Capo Squadriglia non vede gestione né sistema', () => {
    const sezioni = vociMenu(utente('csq', { puo_vedere_diari: true }))
    expect(sezioni).toHaveLength(1)
    expect(sezioni[0]!.voci.map((v) => v.to)).toEqual(['/', '/diari', '/helpdesk'])
  })

  it('la Pattuglia vede i diari assegnati', () => {
    const sezioni = vociMenu(utente('pgv'))
    expect(sezioni[0]!.voci[1]!.etichetta).toBe('Diari assegnati')
  })

  it("le voci di sistema seguono il flag del backend", () => {
    const sezioni = vociMenu(utente('admin', { puo_vedere_impostazioni: true }))
    expect(sezioni.find((s) => s.titolo === 'Sistema')?.voci.length).toBeGreaterThan(0)
  })
})
