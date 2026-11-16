/** Alias dei tipi dell'API usati dalle pagine delle impostazioni. */
import type { components } from '@/api/schema'

type S = components['schemas']

export type Impostazioni = S['ImpostazioniSchema']
export type FooterLink = S['FooterLinkImpostazioniSchema']
export type PaginaStatica = S['PaginaStaticaSchema']
export type RigaTemplate = S['MailTemplateRigaSchema']
export type TemplateEmail = S['MailTemplateSchema']
export type AccessoBloccato = S['AccessoBloccatoSchema']
export type LogExport = S['LogExportSchema']
export type EdizioneCachePdf = S['EdizioneCachePdfSchema']
export type FilePdf = S['FilePdfSchema']
export type ProgressoTask = S['ProgressoTaskSchema']
export type StatoDrive = S['StatoDriveSchema']
export type Aggiornamenti = S['AggiornamentiSchema']
export type Scelta = S['ScelteSchema']
