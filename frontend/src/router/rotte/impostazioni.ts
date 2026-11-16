import type { RouteRecordRaw } from 'vue-router'

/** Rotte del dominio "impostazioni" (figlie del layout dell'app: percorsi relativi senza "/" iniziale). */

const home = { label: 'Home', to: '/' }
const impostazioni = { label: 'Impostazioni', to: '/impostazioni' }

export const rotte: RouteRecordRaw[] = [
  {
    path: 'impostazioni/drive',
    name: 'impostazioni-drive',
    component: () => import('@/views/impostazioni/ImpostazioniDriveView.vue'),
    meta: { titolo: 'Google Drive', breadcrumb: [home, impostazioni, { label: 'Google Drive' }] },
  },
  {
    path: 'impostazioni/cache-pdf',
    name: 'impostazioni-cache-pdf',
    component: () => import('@/views/impostazioni/ImpostazioniCachePdfView.vue'),
    meta: { titolo: 'Cache PDF', breadcrumb: [home, impostazioni, { label: 'Cache PDF' }] },
  },
  {
    path: 'impostazioni/log-export',
    name: 'impostazioni-log-export',
    component: () => import('@/views/impostazioni/ImpostazioniLogExportView.vue'),
    meta: { titolo: 'Log export', breadcrumb: [home, impostazioni, { label: 'Log export' }] },
  },
  {
    path: 'impostazioni/aggiornamenti',
    name: 'impostazioni-aggiornamenti',
    component: () => import('@/views/impostazioni/ImpostazioniAggiornamentiView.vue'),
    meta: { titolo: 'Aggiornamenti', breadcrumb: [home, impostazioni, { label: 'Aggiornamenti' }] },
  },
  {
    path: 'impostazioni/mail/:chiave',
    name: 'impostazioni-mail',
    component: () => import('@/views/impostazioni/ImpostazioniTemplateEmailView.vue'),
    props: true,
    meta: {
      titolo: 'Template email',
      breadcrumb: [home, impostazioni, { label: 'Template email', to: '/impostazioni/template-email' }, { label: 'Modifica' }],
    },
  },
  {
    path: 'impostazioni/pagine/:slug',
    name: 'impostazioni-pagina',
    component: () => import('@/views/impostazioni/ImpostazioniPaginaView.vue'),
    props: true,
    meta: {
      titolo: 'Pagina legale',
      breadcrumb: [home, impostazioni, { label: 'Pagine legali', to: '/impostazioni/pagine' }, { label: 'Modifica' }],
    },
  },
  {
    // Una scheda per percorso: /impostazioni/email è anche la destinazione della callback Gmail OAuth
    path: 'impostazioni/:scheda(generale|email|sicurezza|sistema|template-email|pagine)?',
    name: 'impostazioni',
    component: () => import('@/views/impostazioni/ImpostazioniView.vue'),
    meta: { titolo: 'Impostazioni', breadcrumb: [home, { label: 'Impostazioni' }] },
  },
  {
    path: 'pagine/:slug',
    name: 'impostazioni-pagina-pubblica',
    component: () => import('@/views/impostazioni/PaginaStaticaView.vue'),
    props: true,
    meta: { pubblica: true },
  },
]
