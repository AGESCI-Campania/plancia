import type { FlagMenu, Me } from '@/api/tipi'

export interface VoceMenu {
  etichetta: string
  icona: string
  to: string
  /** Link a una pagina servita da Django (admin, proxy): fuori dal router della SPA. */
  esterno?: boolean
}

export interface SezioneMenu {
  titolo?: string
  voci: VoceMenu[]
}

/**
 * Voci della sidebar per il ruolo attivo. Le condizioni sono i flag calcolati dal backend
 * (`/api/v1/me`, `puo_*`): qui solo la presentazione, nessuna regola di permesso.
 */
export function vociMenu(me: Me): SezioneMenu[] {
  const flag = (nome: FlagMenu) => me.menu?.[nome] ?? false
  const ruolo = me.ruolo.chiave
  const principali: VoceMenu[] = [{ etichetta: 'Home', icona: 'house-fill', to: '/' }]
  if (ruolo === 'pgv') {
    principali.push({ etichetta: 'Diari assegnati', icona: 'journal-check', to: '/diari' })
  } else if (flag('puo_vedere_diari')) {
    principali.push({ etichetta: 'Diari', icona: 'journal-text', to: '/diari' })
  }
  if (flag('puo_gestire_inviti_crp')) {
    principali.push({ etichetta: 'Inviti', icona: 'envelope', to: '/inviti' })
  }
  principali.push({ etichetta: 'Helpdesk', icona: 'headset', to: '/helpdesk' })

  const gestione: VoceMenu[] = []
  if (flag('puo_gestire_edizioni')) gestione.push({ etichetta: 'Edizioni', icona: 'calendar3', to: '/edizioni' })
  if (flag('puo_vedere_utenti')) gestione.push({ etichetta: 'Utenti', icona: 'people', to: '/utenti' })
  if (flag('puo_gestire_inviti')) gestione.push({ etichetta: 'Inviti', icona: 'envelope', to: '/gestione/inviti' })
  if (flag('puo_importare')) gestione.push({ etichetta: 'Import', icona: 'upload', to: '/import' })
  if (flag('puo_vedere_statistiche')) gestione.push({ etichetta: 'Statistiche', icona: 'bar-chart', to: '/statistiche' })

  const sistema: VoceMenu[] = []
  if (flag('puo_vedere_impostazioni')) {
    sistema.push(
      { etichetta: 'Impostazioni', icona: 'sliders', to: '/impostazioni' },
      { etichetta: 'Cache PDF', icona: 'file-earmark-pdf', to: '/impostazioni/cache-pdf' },
      { etichetta: 'Log export', icona: 'journal-text', to: '/impostazioni/log-export' },
      { etichetta: 'Aggiornamenti', icona: 'cloud-arrow-down', to: '/impostazioni/aggiornamenti' },
    )
  }
  if (flag('puo_usare_admin_django')) {
    sistema.push(
      { etichetta: 'Pannello admin', icona: 'shield-lock', to: '/admin/', esterno: true },
      { etichetta: 'Flower', icona: 'diagram-3', to: '/celery/', esterno: true },
      { etichetta: 'Mailpit', icona: 'envelope-open', to: '/mailadmin/', esterno: true },
    )
  }

  return [
    { voci: principali },
    ...(gestione.length ? [{ titolo: 'Gestione', voci: gestione }] : []),
    ...(sistema.length ? [{ titolo: 'Sistema', voci: sistema }] : []),
  ]
}
