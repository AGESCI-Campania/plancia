import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "helpdesk" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
export const rotte: RouteRecordRaw[] = [
  {
    path: 'helpdesk',
    name: 'helpdesk-elenco',
    component: () => import('@/views/helpdesk/HelpdeskElencoView.vue'),
    meta: { titolo: 'Helpdesk', breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Helpdesk' }] },
  },
  {
    path: 'helpdesk/nuovo',
    name: 'helpdesk-nuovo',
    component: () => import('@/views/helpdesk/HelpdeskNuovoView.vue'),
    meta: {
      titolo: 'Nuovo ticket',
      breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Helpdesk', to: '/helpdesk' }, { label: 'Nuovo ticket' }],
    },
  },
  {
    path: 'helpdesk/:id(\\d+)',
    name: 'helpdesk-dettaglio',
    component: () => import('@/views/helpdesk/HelpdeskDettaglioView.vue'),
    props: (to) => ({ id: Number(to.params.id) }),
    meta: {
      titolo: 'Ticket',
      breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Helpdesk', to: '/helpdesk' }, { label: 'Ticket' }],
    },
  },
]
