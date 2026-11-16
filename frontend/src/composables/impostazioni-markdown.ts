/**
 * Markdown → HTML per le note di rilascio (da GitHub): un sottoinsieme semplice (titoli,
 * elenchi, paragrafi, grassetto, corsivo, codice, link http/https). Tutto il testo viene
 * prima reso innocuo (escape), quindi l'HTML del markdown non passa mai: il risultato può
 * andare in `v-html` senza rischi.
 */

function escape(testo: string): string {
  return testo
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

/** Formattazione in linea su testo già passato da `escape`. */
function inLinea(testo: string): string {
  // Il codice prima: il suo contenuto non va interpretato
  const codici: string[] = []
  let t = testo.replace(/`([^`]+)`/g, (_m, c: string) => {
    codici.push(`<code>${c}</code>`)
    return `\u0000${codici.length - 1}\u0000`
  })
  t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_m, etichetta: string, url: string) =>
    `<a href="${url}" target="_blank" rel="noopener noreferrer">${etichetta}</a>`,
  )
  t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/__([^_]+)__/g, '<strong>$1</strong>')
  t = t.replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>').replace(/(^|[^_\w])_([^_\s][^_]*)_/g, '$1<em>$2</em>')
  return t.replace(/\u0000(\d+)\u0000/g, (_m, i: string) => codici[Number(i)] ?? '')
}

export function markdownSicuro(markdown: string): string {
  const righe = escape(markdown ?? '').replace(/\r\n?/g, '\n').split('\n')
  const out: string[] = []
  let paragrafo: string[] = []
  let elenco: 'ul' | 'ol' | null = null

  const chiudiParagrafo = () => {
    if (paragrafo.length) out.push(`<p>${inLinea(paragrafo.join(' '))}</p>`)
    paragrafo = []
  }
  const chiudiElenco = () => {
    if (elenco) out.push(`</${elenco}>`)
    elenco = null
  }

  for (const riga of righe) {
    const r = riga.trim()
    const titolo = /^(#{1,6})\s+(.*)$/.exec(r)
    const puntato = /^[-*+]\s+(.*)$/.exec(r)
    const numerato = /^\d+[.)]\s+(.*)$/.exec(r)
    if (!r) {
      chiudiParagrafo()
      chiudiElenco()
    } else if (titolo) {
      chiudiParagrafo()
      chiudiElenco()
      // h1/h2 del markdown diventano h3: la pagina ha già i suoi titoli
      const livello = Math.min(6, titolo[1]!.length + 2)
      out.push(`<h${livello}>${inLinea(titolo[2]!)}</h${livello}>`)
    } else if (puntato || numerato) {
      chiudiParagrafo()
      const tipo = puntato ? 'ul' : 'ol'
      if (elenco !== tipo) {
        chiudiElenco()
        out.push(`<${tipo}>`)
        elenco = tipo
      }
      out.push(`<li>${inLinea((puntato ?? numerato)![1]!)}</li>`)
    } else if (/^(-{3,}|\*{3,})$/.test(r)) {
      chiudiParagrafo()
      chiudiElenco()
      out.push('<hr>')
    } else {
      chiudiElenco()
      paragrafo.push(r)
    }
  }
  chiudiParagrafo()
  chiudiElenco()
  return out.join('\n')
}
