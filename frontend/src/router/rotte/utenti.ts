import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "utenti" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
export const rotte: RouteRecordRaw[] = [
  {
    path: 'utenti',
    name: 'utenti-elenco',
    component: () => import('@/views/utenti/UtentiElencoView.vue'),
    meta: { titolo: 'Utenti', breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Utenti' }] },
  },
  {
    path: 'utenti/nuovo',
    name: 'utenti-nuovo',
    component: () => import('@/views/utenti/UtentiNuovoView.vue'),
    meta: {
      titolo: 'Nuovo utente',
      breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Utenti', to: '/utenti' }, { label: 'Nuovo utente' }],
    },
  },
  {
    path: 'utenti/:id(\\d+)',
    name: 'utenti-dettaglio',
    component: () => import('@/views/utenti/UtentiDettaglioView.vue'),
    props: (to) => ({ id: Number(to.params.id) }),
    meta: {
      titolo: 'Utente',
      breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Utenti', to: '/utenti' }, { label: 'Dettaglio' }],
    },
  },
]
