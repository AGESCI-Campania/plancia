import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '@/api/http'
import type { Sito } from '@/api/tipi'

const CHIAVE_COPIA = 'plancia:sito'

/**
 * Dati pubblici del sito (`/api/v1/sito`): titolo, footer, manutenzione, provider di login e
 * versione del server. Una copia resta nel browser per mostrare titolo e footer offline, ma
 * `versioneServer` è solo quella appena letta dal server: una copia vecchia non deve far
 * credere che ci sia (o non ci sia) un aggiornamento.
 */
export const useSitoStore = defineStore('sito', () => {
  const sito = ref<Sito | null>(leggiCopia())
  const versioneServer = ref('')

  async function carica(): Promise<void> {
    try {
      const dati = await api.get<Sito>('/sito')
      sito.value = dati
      versioneServer.value = dati.versione ?? ''
      try {
        localStorage.setItem(CHIAVE_COPIA, JSON.stringify(dati))
      } catch {
        // spazio pieno o storage bloccato: la copia è solo una comodità
      }
    } catch {
      versioneServer.value = ''
    }
  }

  return { sito, versioneServer, carica }
})

function leggiCopia(): Sito | null {
  try {
    const testo = localStorage.getItem(CHIAVE_COPIA)
    return testo ? (JSON.parse(testo) as Sito) : null
  } catch {
    return null
  }
}
