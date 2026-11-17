/** Conferma prima di un'azione irreversibile, con la finestra di `ConfermaDialogo.vue` (in App.vue). */
import { ref } from 'vue'

export interface RichiestaConferma {
  titolo: string
  messaggio: string
  conferma: string
  pericolosa: boolean
  risolvi: (ok: boolean) => void
}

export const richiestaConferma = ref<RichiestaConferma | null>(null)

export function conferma(
  messaggio: string,
  { titolo = 'Conferma', testoConferma = 'Conferma', pericolosa = false } = {},
): Promise<boolean> {
  return new Promise((risolvi) => {
    richiestaConferma.value = { titolo, messaggio, conferma: testoConferma, pericolosa, risolvi }
  })
}
