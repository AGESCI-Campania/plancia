import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "moduli" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */
const briciole = (voce: string) => [{ label: 'Home', to: '/' }, { label: 'Diari', to: '/diari' }, { label: voce }]

export const rotte: RouteRecordRaw[] = [
  {
    path: 'diari/:id(\\d+)/anagrafica',
    name: 'moduli-anagrafica',
    component: () => import('@/views/moduli/ModuloAnagraficaView.vue'),
    props: true,
    meta: { titolo: 'Anagrafica', breadcrumb: briciole('Anagrafica') },
  },
  {
    path: 'diari/:id(\\d+)/presentazione',
    name: 'moduli-presentazione',
    component: () => import('@/views/moduli/ModuloPresentazioneView.vue'),
    props: true,
    meta: { titolo: 'Presentazione della squadriglia', breadcrumb: briciole('Presentazione') },
  },
  {
    path: 'diari/:id(\\d+)/imprese/:numero(1|2)',
    name: 'moduli-impresa',
    component: () => import('@/views/moduli/ModuloImpresaView.vue'),
    props: true,
    meta: { titolo: 'Impresa', breadcrumb: briciole('Impresa') },
  },
  {
    path: 'diari/:id(\\d+)/missione',
    name: 'moduli-missione',
    component: () => import('@/views/moduli/ModuloMissioneView.vue'),
    props: true,
    meta: { titolo: 'Missione', breadcrumb: briciole('Missione') },
  },
  {
    path: 'diari/:id(\\d+)/relazione-finale',
    name: 'moduli-relazione-finale',
    component: () => import('@/views/moduli/ModuloRelazioneFinaleView.vue'),
    props: true,
    meta: { titolo: 'Relazione finale', breadcrumb: briciole('Relazione finale') },
  },
  {
    path: 'diari/:id(\\d+)/allegati',
    name: 'moduli-allegati',
    component: () => import('@/views/moduli/AllegatiDiarioView.vue'),
    props: true,
    meta: { titolo: 'Foto del diario', breadcrumb: briciole('Foto') },
  },
]
