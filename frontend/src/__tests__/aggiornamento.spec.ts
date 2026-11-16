import { describe, expect, it } from 'vitest'

import { versioneInferiore } from '@/pwa/aggiornamento'

describe('versioneInferiore', () => {
  it('confronta X.Y.Z numericamente', () => {
    expect(versioneInferiore('3.0.0', '3.0.1')).toBe(true)
    expect(versioneInferiore('3.0.9', '3.0.10')).toBe(true)
    expect(versioneInferiore('3.1.0', '3.0.10')).toBe(false)
    expect(versioneInferiore('3.0.0', '3.0.0')).toBe(false)
  })

  it('ignora i formati sconosciuti', () => {
    expect(versioneInferiore('3.0.0', '')).toBe(false)
    expect(versioneInferiore('3.0.0', '3.1.0rc1')).toBe(false)
  })
})
