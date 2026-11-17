import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "diari" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
export const rotte: RouteRecordRaw[] = [
  {
    path: 'diari',
    name: 'diari-elenco',
    component: () => import('@/views/diari/DiariElencoView.vue'),
    meta: { titolo: 'Diari', breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Diari' }] },
  },
  {
    path: 'diari/:id(\\d+)',
    name: 'diari-dettaglio',
    component: () => import('@/views/diari/DiarioDettaglioView.vue'),
    props: (r) => ({ id: Number(r.params.id) }),
    meta: {
      titolo: 'Diario',
      breadcrumb: [
        { label: 'Home', to: '/' },
        { label: 'Diari', to: '/diari' },
        { label: 'Diario' },
      ],
    },
  },
  {
    path: 'diari/:id(\\d+)/pdf',
    name: 'diari-pdf',
    component: () => import('@/views/diari/DiarioPdfView.vue'),
    props: (r) => ({ id: Number(r.params.id) }),
    meta: {
      titolo: 'PDF del diario',
      breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Diari', to: '/diari' }, { label: 'PDF' }],
    },
  },
  {
    path: 'reparti/:id(\\d+)/cambia-capo-reparto',
    name: 'diari-cambia-crp-reparto',
    component: () => import('@/views/diari/CambiaCapoRepartoView.vue'),
    props: (r) => ({ id: Number(r.params.id) }),
    meta: {
      titolo: 'Cambia Capo Reparto',
      breadcrumb: [
        { label: 'Home', to: '/' },
        { label: 'Diari', to: '/diari' },
        { label: 'Cambia Capo Reparto' },
      ],
    },
  },
]
