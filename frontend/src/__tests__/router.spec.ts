import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import { rotte } from '@/router'

const router = createRouter({ history: createMemoryHistory(), routes: rotte })

describe('rotte', () => {
  it('la home è la pagina dell’app, non un layout pubblico vuoto', () => {
    const r = router.resolve('/')
    expect(r.name).toBe('home')
    expect(r.matched.some((m) => m.meta.pubblica)).toBe(false)
  })

  it('i link delle email aprono le pagine pubbliche', () => {
    expect(router.resolve('/password/reset/abc').name).toBe('reset-password')
    expect(router.resolve('/invito/123e4567-e89b-12d3-a456-426614174000').name).toBe('attivazione-invito')
    expect(router.resolve('/email/verifica/k').name).toBe('verifica-email')
  })
})
