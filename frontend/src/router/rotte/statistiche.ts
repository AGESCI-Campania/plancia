import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "statistiche" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
export const rotte: RouteRecordRaw[] = [
  {
    path: 'statistiche',
    name: 'statistiche',
    component: () => import('@/views/statistiche/StatisticheView.vue'),
    meta: { titolo: 'Statistiche', breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Statistiche' }] },
  },
]
