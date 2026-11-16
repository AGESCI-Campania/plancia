# Icona della PWA di Plancia 3.0 — bozze approvate

Sorgenti approvati dell'icona "Diario di bordo" (decisione del piano 3.0, Fase 3). Le icone
definitive del frontend vanno generate **da questi file**, senza ridisegnarle.

| File | Uso |
|---|---|
| `icona-diario-grande.svg` | dai 180 px in su: icona Home, `apple-touch-icon` (180), 192, 512, splash |
| `icona-diario-piccola.svg` | sotto i 180 px: favicon, 32, 48, 64 px (senza emblema, illeggibile a quelle misure) |
| `emblema-campania.png` | emblema di AGESCI Campania a colori (dal tema, `agesci_theme/img/emblemi/EMBLEMA_CAMPANIA.png`), usato dalla versione grande |
| `anteprima-*-512.png` | resa di riferimento a 512 px, per confronto visivo |

Geometria (viewBox 0–100): fondo `rx 22` verde E/G `#3D8E33`; quaderno bianco `24,18 52×66 rx 6`;
dorso `31,18 4×66` verde al 35%; righe verdi spesse 3,5 a `y` 52, 61, 70; segnalibro giallo oro
`#FFCC1E` `M56 18 V44 L62 38 L68 44 V18 Z`; emblema `35,5,21 20×20`.

Da produrre in Fase 3: PNG 32/48/64/180/192/512, variante *maskable* per Android (contenuto entro
l'area di sicurezza dell'80%, fondo verde a pieno quadrato), favicon, `theme_color` `#3D8E33`.
Nel PNG finale l'emblema va incorporato (lo SVG grande lo referenzia come file accanto).
