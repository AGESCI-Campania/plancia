/**
 * Tipi delle risposte dell'API, dagli schemi generati da OpenAPI (`npm run api:tipi` →
 * src/api/schema.d.ts, da rigenerare quando cambiano gli schemi del backend).
 */
import type { components } from './schema'

type Schemi = components['schemas']

export type Me = Schemi['MeEstesoSchema']
export type Menu = Schemi['MenuSchema']
export type Ruolo = Schemi['RuoloSchema']
export type Sito = Schemi['SitoSchema']

/** Nome di un flag di menu calcolato dal backend (`me.menu`). */
export type FlagMenu = keyof Menu
