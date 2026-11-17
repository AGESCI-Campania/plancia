// Genera le icone della PWA in public/icone/ dai sorgenti approvati in ../docs/icona-pwa/
// (decisione del piano 3.0: generarle da lì, senza ridisegnarle). Uso: npm run icone
import { mkdir, readFile, writeFile } from 'node:fs/promises'

import sharp from 'sharp'

const SORGENTI = new URL('../../docs/icona-pwa/', import.meta.url)
const DESTINAZIONE = new URL('../public/icone/', import.meta.url)

const piccola = await readFile(new URL('icona-diario-piccola.svg', SORGENTI), 'utf8')
const emblema = await readFile(new URL('emblema-campania.png', SORGENTI))
// La versione grande referenzia l'emblema come file accanto, che il renderer SVG di sharp
// non carica: si toglie dallo SVG e si sovrappone come immagine, con la stessa geometria
// (20×20 su viewBox 100, a 35,5/21 da sinistra/alto).
const grande = (await readFile(new URL('icona-diario-grande.svg', SORGENTI), 'utf8')).replace(
  /<image [^>]*\/>/,
  '',
)
const EMBLEMA = { x: 35.5, y: 21, lato: 20 }

/** Maskable Android: fondo verde a pieno quadrato, disegno nell'80% centrale (area sicura). */
const MASKABLE = { scala: 0.8, spostamento: 10 }
const maskable = grande
  .replace(
    '<rect width="100" height="100" rx="22" fill="#3D8E33"/>',
    `<rect width="100" height="100" fill="#3D8E33"/><g transform="translate(${MASKABLE.spostamento} ${MASKABLE.spostamento}) scale(${MASKABLE.scala})">`,
  )
  .replace('</svg>', '</g></svg>')

async function png(svg, lato, nome, conEmblema = null) {
  let immagine = sharp(Buffer.from(svg), { density: 72 * Math.ceil(lato / 100) * 2 }).resize(lato, lato)
  if (conEmblema) {
    const { scala = 1, spostamento = 0 } = conEmblema
    const u = (lato / 100) * scala
    const latoEmblema = Math.round(EMBLEMA.lato * u)
    const sopra = await sharp(emblema).resize(latoEmblema, latoEmblema).png().toBuffer()
    immagine = sharp(await immagine.png().toBuffer()).composite([
      {
        input: sopra,
        left: Math.round((lato / 100) * spostamento + EMBLEMA.x * u),
        top: Math.round((lato / 100) * spostamento + EMBLEMA.y * u),
      },
    ])
  }
  await immagine.png({ compressionLevel: 9 }).toFile(new URL(nome, DESTINAZIONE).pathname)
}

await mkdir(DESTINAZIONE, { recursive: true })
for (const lato of [32, 48, 64]) await png(piccola, lato, `icona-${lato}.png`)
for (const lato of [180, 192, 512]) await png(grande, lato, `icona-${lato}.png`, {})
await png(maskable, 512, 'icona-maskable-512.png', MASKABLE)
await writeFile(new URL('icona-piccola.svg', DESTINAZIONE), piccola)
console.log('Icone generate in public/icone/')
