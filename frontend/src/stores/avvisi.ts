import { defineStore } from 'pinia'
import { ref } from 'vue'

export type TipoAvviso = 'success' | 'danger' | 'warning' | 'info'

export interface Avviso {
  id: number
  tipo: TipoAvviso
  testo: string
}

/** Avvisi temporanei (toast) dopo un'azione: "Diario inviato", "Impostazioni salvate"… */
export const useAvvisiStore = defineStore('avvisi', () => {
  const avvisi = ref<Avviso[]>([])
  let prossimo = 1

  function mostra(testo: string, tipo: TipoAvviso = 'success', durataMs = 5000): void {
    const id = prossimo++
    avvisi.value.push({ id, tipo, testo })
    if (durataMs > 0) setTimeout(() => chiudi(id), durataMs)
  }

  function chiudi(id: number): void {
    avvisi.value = avvisi.value.filter((a) => a.id !== id)
  }

  return { avvisi, mostra, chiudi }
})
