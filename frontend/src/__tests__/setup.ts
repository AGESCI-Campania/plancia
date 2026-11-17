import 'fake-indexeddb/auto'
import { vi } from 'vitest'

// Il registro del service worker non esiste in jsdom.
vi.mock('virtual:pwa-register/vue', async () => {
  const { ref } = await import('vue')
  return { useRegisterSW: () => ({ needRefresh: ref(false), offlineReady: ref(false), updateServiceWorker: vi.fn() }) }
})

;(globalThis as { __VERSIONE_APP__?: string }).__VERSIONE_APP__ = '3.0.0'
