import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "profilo" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
export const rotte: RouteRecordRaw[] = [
  {
    path: 'profilo',
    name: 'profilo',
    component: () => import('@/views/profilo/ProfiloView.vue'),
    meta: { titolo: 'Il mio profilo', breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Il mio profilo' }] },
  },
]
