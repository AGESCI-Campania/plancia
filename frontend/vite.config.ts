import { readFile } from 'node:fs/promises'
import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'
import { VitePWA } from 'vite-plugin-pwa'

/** La versione dell'app è quella del backend: una sola fonte, ../pyproject.toml. */
async function versioneApp(): Promise<string> {
  const pyproject = await readFile(new URL('../pyproject.toml', import.meta.url), 'utf8')
  const trovata = /^version\s*=\s*"([^"]+)"/m.exec(pyproject)
  if (!trovata?.[1]) throw new Error('Versione non trovata in pyproject.toml')
  return trovata[1]
}

// In sviluppo Django gira su :8000; la SPA chiama gli stessi percorsi che in produzione
// smista l'nginx interno (vedi deploy/nginx/default.conf.template).
const BACKEND = process.env.PLANCIA_BACKEND ?? 'http://localhost:8000'
const PERCORSI_BACKEND = [
  '/api',
  '/_allauth',
  '/accounts',
  '/admin',
  '/static',
  '/media',
  '/drive/oauth/callback',
  '/impostazioni/gmail-smtp/oauth/callback',
  '/hijack',
  '/healthz',
]

export default defineConfig({
  define: { __VERSIONE_APP__: JSON.stringify(await versioneApp()) },
  plugins: [
    vue(),
    VitePWA({
      // "prompt": la nuova versione si installa solo quando l'utente accetta, così nessuno
      // perde un modulo a metà (vedi src/pwa/aggiornamento.ts e AggiornamentoApp.vue).
      registerType: 'prompt',
      injectRegister: false,
      manifest: {
        name: 'Plancia — Guidoncini Verdi',
        short_name: 'Plancia',
        description: 'Gestione Guidoncini Verdi - AGESCI Campania',
        lang: 'it-IT',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        theme_color: '#3D8E33',
        background_color: '#ffffff',
        icons: [
          { src: '/icone/icona-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icone/icona-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icone/icona-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Solo la shell dell'app: mai risposte delle API in cache (dati personali, regole di
        // visibilità): l'offline dei moduli passa da Dexie (src/offline/).
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [
          /^\/api\//,
          /^\/_allauth\//,
          /^\/accounts\//,
          /^\/admin\//,
          /^\/static\//,
          /^\/media\//,
          /^\/drive\//,
          /^\/hijack\//,
          /^\/impostazioni\/gmail-smtp\//,
          /^\/mailadmin/,
          /^\/celery/,
          /^\/anymail\//,
          /^\/healthz/,
        ],
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  css: {
    preprocessorOptions: { scss: { quietDeps: true } },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      PERCORSI_BACKEND.map((percorso) => [percorso, { target: BACKEND, changeOrigin: false }]),
    ),
  },
  build: { target: ['safari18', 'chrome130', 'firefox132'] },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    setupFiles: ['src/__tests__/setup.ts'],
  },
})
