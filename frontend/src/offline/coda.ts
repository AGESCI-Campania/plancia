/**
 * Coda delle modifiche fatte offline (outbox). L'implementazione con Dexie arriva in Fase 5:
 * qui il contratto usato da chi deve sapere se ci sono invii in attesa (aggiornamento della
 * PWA, logout, banner).
 */
import { ref } from 'vue'

/** Numero di modifiche (moduli, foto) non ancora inviate al server. */
export const inAttesa = ref(0)

/** Prova a inviare tutto ciò che è in coda; restituisce quante modifiche restano. */
export async function sincronizzaCoda(): Promise<number> {
  return inAttesa.value
}
