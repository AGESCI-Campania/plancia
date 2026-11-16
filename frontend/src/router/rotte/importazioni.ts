import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "importazioni" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
export const rotte: RouteRecordRaw[] = [
  {
    path: 'import',
    name: 'importazioni',
    component: () => import('@/views/importazioni/ImportazioniView.vue'),
    meta: { titolo: 'Import tracciati', breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Import' }] },
  },
  {
    path: 'import/:id(\\d+)',
    name: 'importazioni-dettaglio',
    component: () => import('@/views/importazioni/ImportazioniDettaglioView.vue'),
    props: true,
    meta: {
      titolo: 'Dettaglio import',
      breadcrumb: [
        { label: 'Home', to: '/' },
        { label: 'Import', to: '/import' },
        { label: 'Dettaglio import' },
      ],
    },
  },
]
