import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "edizioni" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
const home = { label: 'Home', to: '/' }
const elenco = { label: 'Edizioni', to: '/edizioni' }

export const rotte: RouteRecordRaw[] = [
  {
    path: 'edizioni',
    name: 'edizioni-elenco',
    component: () => import('@/views/edizioni/EdizioniElencoView.vue'),
    meta: { titolo: 'Edizioni', breadcrumb: [home, { label: 'Edizioni' }] },
  },
  {
    path: 'edizioni/nuova',
    name: 'edizioni-nuova',
    component: () => import('@/views/edizioni/EdizioneFormView.vue'),
    meta: { titolo: 'Nuova edizione', breadcrumb: [home, elenco, { label: 'Nuova edizione' }] },
  },
  {
    path: 'edizioni/:id(\\d+)',
    name: 'edizioni-dettaglio',
    component: () => import('@/views/edizioni/EdizioneDettaglioView.vue'),
    props: (r) => ({ id: Number(r.params.id) }),
    meta: { titolo: 'Edizione', breadcrumb: [home, elenco, { label: 'Dettaglio' }] },
  },
  {
    path: 'edizioni/:id(\\d+)/modifica',
    name: 'edizioni-modifica',
    component: () => import('@/views/edizioni/EdizioneFormView.vue'),
    props: (r) => ({ id: Number(r.params.id) }),
    meta: { titolo: 'Modifica edizione', breadcrumb: [home, elenco, { label: 'Modifica' }] },
  },
]
