/** Ordinamento delle righe della gestione inviti (squadriglia, Capo Squadriglia, Capo Reparto). */
import type { PersonaInvito, RigaInviti } from '@/components/utenti/tipi'

export type ColonnaOrdinamento = 'squadriglia' | 'csq' | 'crp'

const nominativo = (p: PersonaInvito | null | undefined): string => (p ? `${p.cognome} ${p.nome}` : '')

function chiave(r: RigaInviti, colonna: ColonnaOrdinamento): string {
  if (colonna === 'csq') return nominativo(r.csq)
  if (colonna === 'crp') return nominativo(r.crp)
  return r.squadriglia
}

/** Copia ordinata (alfabetica italiana, senza distinguere maiuscole; i vuoti in fondo). */
export function ordinaRighe(righe: readonly RigaInviti[], colonna: ColonnaOrdinamento, crescente = true): RigaInviti[] {
  const confronto = new Intl.Collator('it', { sensitivity: 'base' })
  return [...righe].sort((a, b) => {
    const ka = chiave(a, colonna)
    const kb = chiave(b, colonna)
    if (!ka || !kb) return ka ? -1 : kb ? 1 : 0
    const c = confronto.compare(ka, kb)
    return crescente ? c : -c
  })
}
