/**
 * Rotte della SPA. Le guardie servono solo all'interfaccia (portare al login, alla
 * configurazione della MFA obbligatoria): i permessi veri li controlla il backend.
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import LayoutAccesso from '@/layouts/LayoutAccesso.vue'
import LayoutApp from '@/layouts/LayoutApp.vue'
import { useSessioneStore } from '@/stores/sessione'

// Una lista di rotte per dominio (src/router/rotte/<dominio>.ts), figlie di LayoutApp.
const moduliRotte = import.meta.glob<{ rotte: RouteRecordRaw[] }>('./rotte/*.ts', { eager: true })
const rotteDomini = Object.values(moduliRotte).flatMap((m) => m.rotte)

declare module 'vue-router' {
  interface RouteMeta {
    /** Accessibile senza login. */
    pubblica?: boolean
    /** Solo per chi NON è autenticato (la pagina di accesso). */
    soloAnonimi?: boolean
    titolo?: string
    breadcrumb?: { label: string; to?: string }[]
  }
}

const rottePubbliche: RouteRecordRaw[] = [
  { path: '', name: 'accesso', component: () => import('@/views/auth/AccessoView.vue'), meta: { soloAnonimi: true, titolo: 'Accedi' } },
  { path: 'mfa', name: 'accesso-mfa', component: () => import('@/views/auth/MfaView.vue'), meta: { soloAnonimi: true, titolo: 'Verifica' } },
  { path: 'ritorno', name: 'accesso-ritorno', component: () => import('@/views/auth/RitornoProviderView.vue'), meta: { pubblica: true } },
  { path: 'password', name: 'password-dimenticata', component: () => import('@/views/auth/PasswordDimenticataView.vue'), meta: { pubblica: true, titolo: 'Password dimenticata' } },
  // Percorsi assoluti (link nelle email, HEADLESS_FRONTEND_URLS) con lo stesso layout pubblico
  { path: '/password/reset/:chiave', name: 'reset-password', component: () => import('@/views/auth/ResetPasswordView.vue'), props: true, meta: { pubblica: true, titolo: 'Nuova password' } },
  { path: '/email/verifica/:chiave', name: 'verifica-email', component: () => import('@/views/auth/VerificaEmailView.vue'), props: true, meta: { pubblica: true } },
  { path: '/invito/:token', name: 'attivazione-invito', component: () => import('@/views/auth/AttivazioneInvitoView.vue'), props: true, meta: { pubblica: true, titolo: 'Attivazione' } },
]

export const rotte: RouteRecordRaw[] = [
  { path: '/accesso', component: LayoutAccesso, children: rottePubbliche },
  {
    path: '/',
    component: LayoutApp,
    children: [
      { path: '', name: 'home', component: () => import('@/views/HomeView.vue'), meta: { titolo: 'Home' } },
      {
        path: 'profilo/sicurezza',
        name: 'sicurezza',
        component: () => import('@/views/auth/SicurezzaView.vue'),
        meta: { titolo: 'Password e sicurezza', breadcrumb: [{ label: 'Home', to: '/' }, { label: 'Password e sicurezza' }] },
      },
      ...rotteDomini,
      { path: ':percorso(.*)*', name: 'non-trovata', component: () => import('@/views/NonTrovataView.vue'), meta: { titolo: 'Pagina non trovata' } },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes: rotte,
  scrollBehavior: (_a, _da, salvata) => salvata ?? { top: 0 },
})

router.beforeEach(async (to) => {
  const sessione = useSessioneStore()
  if (!sessione.caricata) {
    try {
      await sessione.carica()
    } catch {
      // Server irraggiungibile: le pagine pubbliche restano raggiungibili, le altre
      // mostrano l'errore quando chiamano le API (Fase 5: dati offline).
    }
  }
  const pubblica = to.matched.some((r) => r.meta.pubblica || r.meta.soloAnonimi)
  if (to.meta.soloAnonimi && sessione.autenticato) return { name: 'home' }
  if (!pubblica && !sessione.autenticato) {
    if (sessione.passoInSospeso === 'mfa_authenticate') return { name: 'accesso-mfa', query: { next: to.fullPath } }
    return { name: 'accesso', query: to.fullPath === '/' ? {} : { next: to.fullPath } }
  }
  // MFA obbligatoria per il ruolo e non ancora configurata: prima la configurazione.
  const me = sessione.me
  if (me?.mfa_da_configurare && to.name !== 'sicurezza' && !pubblica) return { name: 'sicurezza' }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.titolo ? `${to.meta.titolo} · Plancia` : 'Plancia'
})
