/** Tipi delle API di utenti, profilo, inviti e helpdesk (dagli schemi generati). */
import type { components } from '@/api/schema'

type Schemi = components['schemas']

// Utenti e profilo
export type UtenteLista = Schemi['UtenteListaSchema']
export type UtenteDettaglio = Schemi['UtenteDettaglioSchema']
export type UtenteCreato = Schemi['UtenteCreatoSchema']
export type OpzioniUtenti = Schemi['OpzioniUtentiSchema']
export type Nomina = Schemi['NominaSchema']
export type LoginEvent = Schemi['LoginEventSchema']
export type Profilo = Schemi['ProfiloSchema']
export type Sessione = Schemi['SessioneSchema']
export type SocialAccount = Schemi['SocialAccountSchema']
export type SocioBreve = Schemi['SocioBreveSchema']
export type SocioAutocomplete = Schemi['SocioAutocompleteSchema']
export type EdizioneBreve = Schemi['EdizioneSchema']

// Inviti
export type Invito = Schemi['InvitoSchema']
export type RigaInviti = Schemi['RigaInvitiSchema']
export type RiepilogoInviti = Schemi['RiepilogoInvitiSchema']
export type InvitiCrp = Schemi['InvitiCrpSchema']
export type PersonaInvito = Schemi['PersonaInvitoSchema']

// Helpdesk
export type Ticket = Schemi['TicketSchema']
export type TicketDettaglio = Schemi['TicketDettaglioSchema']
export type OpzioniTicket = Schemi['OpzioniTicketSchema']
export type RispostaTicket = Schemi['RispostaSchema']
