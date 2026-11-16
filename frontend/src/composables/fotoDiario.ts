/**
 * Foto dei moduli (1ª e 2ª impresa, missione): elenco, caricamento multiplo da fotocamera o
 * galleria con anteprima, avanzamento ed errore per file, eliminazione con conferma.
 *
 * **Ogni invio passa da `invia`** (default `inviaFotoRete`, multipart con `Idempotency-Key`:
 * un nuovo tentativo della stessa foto non crea doppioni). In Fase 5 la coda offline delle
 * foto sostituisce questa funzione senza cambiare la galleria.
 */
import { onScopeDispose, ref, toValue, type MaybeRefOrGetter } from 'vue'

import { api, ErroreApi, leggiCookie } from '@/api/http'
import type { Allegato } from '@/composables/diarioCompilazione'
import { conferma } from '@/composables/conferma'

export interface InvioFoto {
  diarioId: number | string
  modulo: string
  file: Blob
  nome: string
  /** Idempotency-Key: la stessa per i tentativi ripetuti della stessa foto. */
  chiave: string
}

export interface OpzioniInvio {
  /** Frazione inviata (0–1). */
  avanzamento?: (frazione: number) => void
  segnale?: AbortSignal
}

export type InviaFoto = (invio: InvioFoto, opzioni?: OpzioniInvio) => Promise<Allegato>

function messaggioErrore(stato: number, corpo: unknown): string {
  const c = (corpo ?? {}) as { detail?: string; errori?: Record<string, string[]> }
  const primo = c.errori && Object.values(c.errori).flat()[0]
  if (primo) return primo
  if (c.detail) return c.detail
  if (stato === 0) return 'Sei offline o il server non risponde.'
  if (stato === 413) return 'File troppo grande.'
  return `Errore ${stato}.`
}

/** Invio multipart con XMLHttpRequest (fetch non dà l'avanzamento dell'upload). */
export const inviaFotoRete: InviaFoto = (invio, opzioni = {}) =>
  new Promise((risolvi, rifiuta) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/v1/diari/${invio.diarioId}/allegati`)
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.setRequestHeader('X-CSRFToken', leggiCookie('csrftoken'))
    xhr.setRequestHeader('Idempotency-Key', invio.chiave)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) opzioni.avanzamento?.(e.loaded / e.total)
    }
    xhr.onload = () => {
      let corpo: unknown = null
      try {
        corpo = JSON.parse(xhr.responseText)
      } catch {
        corpo = null
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        opzioni.avanzamento?.(1)
        risolvi(corpo as Allegato)
      } else {
        rifiuta(new ErroreApi(xhr.status, messaggioErrore(xhr.status, corpo), {}, corpo))
      }
    }
    xhr.onerror = () => rifiuta(new ErroreApi(0, messaggioErrore(0, null)))
    xhr.onabort = () => rifiuta(new DOMException('Invio annullato', 'AbortError'))
    opzioni.segnale?.addEventListener('abort', () => xhr.abort())
    const dati = new FormData()
    dati.append('modulo', invio.modulo)
    dati.append('file', invio.file, invio.nome)
    xhr.send(dati)
  })

const TIPI_RICODIFICABILI = new Set(['image/jpeg', 'image/png', 'image/webp'])

/**
 * Riduce la foto al lato massimo `maxPx` (JPEG 0,85) prima dell'invio: meno dati dal telefono.
 * Il server ridimensiona comunque; se il browser non sa decodificarla (es. HEIC fuori da
 * Safari) o è già piccola si invia l'originale.
 */
export async function riduciFoto(file: File, maxPx: number): Promise<{ blob: Blob; nome: string }> {
  const originale = { blob: file as Blob, nome: file.name }
  if (typeof document === 'undefined' || typeof URL.createObjectURL !== 'function') return originale
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    img.src = url
    await img.decode()
    const lato = Math.max(img.naturalWidth, img.naturalHeight)
    if (!lato || (lato <= maxPx && TIPI_RICODIFICABILI.has(file.type))) return originale
    const scala = Math.min(1, maxPx / lato)
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(img.naturalWidth * scala)
    canvas.height = Math.round(img.naturalHeight * scala)
    canvas.getContext('2d')?.drawImage(img, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, 'image/jpeg', 0.85))
    if (!blob) return originale
    return { blob, nome: `${file.name.replace(/\.[^.]*$/, '') || 'foto'}.jpg` }
  } catch {
    return originale
  } finally {
    URL.revokeObjectURL(url)
  }
}

export type StatoInvio = 'attesa' | 'preparazione' | 'invio' | 'errore'

/** Una foto scelta e non ancora sul server. */
export interface VoceInvio {
  id: string
  nome: string
  modulo: string
  file: File
  /** Object URL per l'anteprima locale. */
  anteprima: string
  stato: StatoInvio
  avanzamento: number
  errore: string
  chiave: string
  /** Errore definitivo (tipo, dimensione): riprovare non serve. */
  definitivo: boolean
}

export interface OpzioniGalleria {
  invia?: InviaFoto
  maxPx?: MaybeRefOrGetter<number>
  maxMb?: MaybeRefOrGetter<number>
  tipi?: MaybeRefOrGetter<string[]>
  /** Dopo un caricamento o un'eliminazione riusciti. */
  dopoModifica?: () => void
}

let contatore = 0
const chiaveCasuale = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `f${Date.now()}${++contatore}`

export function formattaDimensione(byte: number): string {
  if (byte < 1024) return `${byte} B`
  if (byte < 1024 * 1024) return `${Math.round(byte / 1024)} KB`
  return `${(byte / 1024 / 1024).toFixed(1).replace('.', ',')} MB`
}

export function useGalleriaFoto(diarioId: number | string, modulo: string, opzioni: OpzioniGalleria = {}) {
  const invia = opzioni.invia ?? inviaFotoRete
  const foto = ref<Allegato[]>([])
  const invii = ref<VoceInvio[]>([])
  const caricamento = ref(false)
  const errore = ref('')
  let codaAttiva = false

  async function carica(): Promise<void> {
    caricamento.value = true
    errore.value = ''
    try {
      foto.value = await api.get<Allegato[]>(`/diari/${diarioId}/allegati`, { modulo })
    } catch (e) {
      errore.value = e instanceof Error ? e.message : 'Errore imprevisto.'
    } finally {
      caricamento.value = false
    }
  }

  function controlla(file: File): string {
    const maxMb = toValue(opzioni.maxMb) ?? 20
    const tipi = toValue(opzioni.tipi) ?? []
    if (tipi.length && file.type && !tipi.includes(file.type)) return `Tipo non consentito (${file.type}).`
    if (file.size > maxMb * 1024 * 1024) return `Supera il limite di ${maxMb} MB.`
    return ''
  }

  /** Aggiunge alla coda le foto scelte e le invia una alla volta. */
  function aggiungi(file: Iterable<File>): void {
    for (const f of file) {
      const problema = controlla(f)
      invii.value.push({
        id: `i${++contatore}`,
        nome: f.name,
        modulo,
        file: f,
        anteprima: URL.createObjectURL(f),
        stato: problema ? 'errore' : 'attesa',
        avanzamento: 0,
        errore: problema,
        chiave: chiaveCasuale(),
        definitivo: Boolean(problema),
      })
    }
    void svuotaCoda()
  }

  function voce(id: string): VoceInvio | undefined {
    return invii.value.find((v) => v.id === id)
  }

  function togli(id: string): void {
    const v = voce(id)
    if (v) URL.revokeObjectURL(v.anteprima)
    invii.value = invii.value.filter((x) => x.id !== id)
  }

  async function inviaVoce(id: string): Promise<void> {
    const v = voce(id)
    if (!v) return
    v.stato = 'preparazione'
    v.errore = ''
    v.avanzamento = 0
    try {
      const { blob, nome } = await riduciFoto(v.file, toValue(opzioni.maxPx) ?? 1024)
      const corrente = voce(id)
      if (!corrente) return
      corrente.stato = 'invio'
      const allegato = await invia(
        { diarioId, modulo, file: blob, nome, chiave: corrente.chiave },
        { avanzamento: (f) => (corrente.avanzamento = f) },
      )
      foto.value = [...foto.value.filter((a) => a.id !== allegato.id), allegato]
      togli(id)
      opzioni.dopoModifica?.()
    } catch (e) {
      const corrente = voce(id)
      if (!corrente) return
      corrente.stato = 'errore'
      corrente.errore = e instanceof Error ? e.message : 'Errore imprevisto.'
      corrente.definitivo = e instanceof ErroreApi && [400, 403, 413, 415, 422].includes(e.stato)
    }
  }

  async function svuotaCoda(): Promise<void> {
    if (codaAttiva) return
    codaAttiva = true
    try {
      let prossima = invii.value.find((v) => v.stato === 'attesa')
      while (prossima) {
        await inviaVoce(prossima.id)
        prossima = invii.value.find((v) => v.stato === 'attesa')
      }
    } finally {
      codaAttiva = false
    }
  }

  /** Nuovo tentativo di una foto non riuscita (stessa chiave: niente doppioni). */
  function riprova(id: string): void {
    const v = voce(id)
    if (!v) return
    v.stato = 'attesa'
    v.errore = ''
    void svuotaCoda()
  }

  async function elimina(allegato: Allegato): Promise<boolean> {
    const ok = await conferma(`Eliminare la foto «${allegato.nome}»? L'operazione non si può annullare.`, {
      titolo: 'Elimina foto',
      testoConferma: 'Elimina',
      pericolosa: true,
    })
    if (!ok) return false
    try {
      await api.delete(`/diari/${diarioId}/allegati/${allegato.id}`)
    } catch (e) {
      if (!(e instanceof ErroreApi && e.stato === 404)) throw e
    }
    foto.value = foto.value.filter((a) => a.id !== allegato.id)
    opzioni.dopoModifica?.()
    return true
  }

  onScopeDispose(() => {
    for (const v of invii.value) URL.revokeObjectURL(v.anteprima)
  })

  return { foto, invii, caricamento, errore, carica, aggiungi, riprova, togli, elimina }
}
