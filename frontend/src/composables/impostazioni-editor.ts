/**
 * Funzioni di supporto per l'editor HTML delle impostazioni (template email, pagine
 * statiche, testo del footer) e per le liste ordinabili.
 */

/** Tag che l'editor visuale (Tiptap con StarterKit + immagini) conserva senza perdite. */
const TAG_SUPPORTATI = new Set([
  'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'del', 'a', 'code', 'pre',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'hr', 'img',
])

/**
 * Vero se l'HTML contiene qualcosa che l'editor visuale perderebbe: tabelle, `div`, stili
 * in linea, documento completo, tag di template Django (`{% for %}`…). In quel caso la
 * modifica parte dal sorgente HTML, che resta intatto.
 */
export function richiedeSorgente(html: string): boolean {
  if (!html) return false
  if (/\{%/.test(html)) return true
  if (/<!doctype/i.test(html)) return true
  if (/\s(style|class|align|bgcolor|width|height|colspan|rowspan)\s*=/i.test(html.replace(/<img\b[^>]*>/gi, ''))) {
    return true
  }
  for (const m of html.matchAll(/<\/?([a-z][a-z0-9]*)\b/gi)) {
    if (!TAG_SUPPORTATI.has(m[1]!.toLowerCase())) return true
  }
  return false
}

/** Testo del segnaposto di un template Django: `nome` → `{{ nome }}`. */
export const segnaposto = (nome: string): string => `{{ ${nome} }}`

/** Inserisce `testo` in `valore` al posto della selezione [inizio, fine]; restituisce testo e cursore. */
export function inserisciInTesto(
  valore: string,
  testo: string,
  inizio: number,
  fine: number = inizio,
): { valore: string; cursore: number } {
  const a = Math.max(0, Math.min(inizio, valore.length))
  const b = Math.max(a, Math.min(fine, valore.length))
  return { valore: valore.slice(0, a) + testo + valore.slice(b), cursore: a + testo.length }
}

/** Copia di `elenco` con l'elemento `indice` spostato di `delta` posizioni (entro i limiti). */
export function sposta<T>(elenco: readonly T[], indice: number, delta: number): T[] {
  const copia = [...elenco]
  const nuovo = indice + delta
  if (indice < 0 || indice >= copia.length || nuovo < 0 || nuovo >= copia.length) return copia
  const [el] = copia.splice(indice, 1)
  copia.splice(nuovo, 0, el as T)
  return copia
}

/** Dimensione di un file leggibile ("1,2 MB"). */
export function dimensioneLeggibile(byte: number | null | undefined): string {
  if (!byte) return '—'
  const unita = ['byte', 'KB', 'MB', 'GB']
  let n = byte
  let i = 0
  while (n >= 1024 && i < unita.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toLocaleString('it-IT', { maximumFractionDigits: i ? 1 : 0 })} ${unita[i]}`
}

/** Data e ora brevi in italiano ("16/11/2026 21:20"), "—" se assente. */
export function dataOra(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
