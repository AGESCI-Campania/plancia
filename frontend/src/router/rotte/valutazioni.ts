import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "valutazioni" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
export const rotte: RouteRecordRaw[] = [
  {
    path: 'diari/:id(\\d+)/valutazione',
    name: 'valutazioni-diario',
    component: () => import('@/views/valutazioni/ValutazioneView.vue'),
    props: (r) => ({ id: Number(r.params.id) }),
    meta: {
      titolo: 'Valutazione',
      breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Diari', to: '/diari' }, { label: 'Valutazione' }],
    },
  },
]
