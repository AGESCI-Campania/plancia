import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "inviti" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
export const rotte: RouteRecordRaw[] = [
  {
    path: 'inviti',
    name: 'inviti-crp',
    component: () => import('@/views/inviti/InvitiCrpView.vue'),
    meta: {
      titolo: 'Inviti Capi Squadriglia',
      breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Inviti Capi Squadriglia' }],
    },
  },
  {
    path: 'gestione/inviti',
    name: 'inviti-gestione',
    component: () => import('@/views/inviti/InvitiGestioneView.vue'),
    meta: { titolo: 'Gestione inviti', breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Gestione inviti' }] },
  },
]
