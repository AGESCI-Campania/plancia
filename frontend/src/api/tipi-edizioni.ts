/** Tipi dell'API per edizioni, home, valutazioni e Google Drive (alias degli schemi generati). */
import type { components } from './schema'

type Schemi = components['schemas']

export type Edizione = Schemi['EdizioneSchema']
export type EdizioneIn = Schemi['EdizioneInSchema']
export type RiepilogoEdizione = Schemi['RiepilogoEdizioneSchema']
export type EdizioneAttiva = Schemi['EdizioneAttivaSchema']
export type StatsDiari = Schemi['StatsDiariSchema']
export type Dilazione = Schemi['DilazioneSchema']
export type PubblicaEsiti = Schemi['PubblicaEsitiSchema']
export type ExportAvviato = Schemi['ExportAvviatoSchema']

export type DiarioRiga = Schemi['DiarioListaSchema']
export type DiarioDettaglio = Schemi['DiarioDettaglioSchema']
export type FiltriDiari = Schemi['FiltriDiariSchema']

export type Valutazione = Schemi['ValutazioneApiSchema']
export type AzioniValutazione = Schemi['AzioniValutazioneSchema']
export type SocioAutocomplete = Schemi['SocioAutocompleteSchema']

export type StatoDrive = Schemi['StatoDriveSchema']
export type Cartella = Schemi['CartellaSchema']
export type CartellaInfo = Schemi['CartellaInfoSchema']
export type DriveEdizione = Schemi['DriveEdizioneSchema']
