import { describe, expect, it } from 'vitest'

import { destinazioneSicura } from '@/composables/destinazione'

describe('destinazioneSicura', () => {
  it('accetta solo percorsi interni', () => {
    expect(destinazioneSicura('/diari/3')).toBe('/diari/3')
    expect(destinazioneSicura('/admin/')).toBe('/admin/')
    expect(destinazioneSicura('https://esempio.org')).toBe('/')
    expect(destinazioneSicura('//esempio.org')).toBe('/')
    expect(destinazioneSicura(undefined)).toBe('/')
  })
})
