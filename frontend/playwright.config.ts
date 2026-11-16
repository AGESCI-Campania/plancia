import { defineConfig, devices } from '@playwright/test'

/** Flussi end-to-end contro lo stack di sviluppo (Django su :8000 + `npm run dev`). */
export default defineConfig({
  testDir: './e2e',
  use: { baseURL: process.env.PLANCIA_E2E_URL ?? 'http://localhost:5173', locale: 'it-IT' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'iphone', use: { ...devices['iPhone 15'] } },
  ],
  webServer: process.env.PLANCIA_E2E_URL
    ? undefined
    : { command: 'npm run dev', url: 'http://localhost:5173', reuseExistingServer: true },
})
