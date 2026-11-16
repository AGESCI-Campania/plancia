/**
 * Scaricamento di file (PDF, Excel, CSV) dall'API. Su iOS in PWA standalone la navigazione
 * verso un file apre Quick Look senza condivisione: si usa `navigator.share({ files })`;
 * altrove un `<a download>` sul blob. Porta la logica di static/js/plancia-file-viewer.js.
 */
import { scarica } from '@/api/http'

export const iosPwa = (): boolean =>
  (navigator as Navigator & { standalone?: boolean }).standalone === true ||
  (window.matchMedia('(display-mode: standalone)').matches && /iPad|iPhone|iPod/.test(navigator.userAgent))

export async function scaricaFile(url: string): Promise<File> {
  const { blob, nome, tipo } = await scarica(url)
  return new File([blob], nome, { type: tipo.split(';')[0] || blob.type })
}

export async function salvaFile(file: File): Promise<void> {
  if (navigator.canShare?.({ files: [file] }) && iosPwa()) {
    try {
      await navigator.share({ files: [file], title: file.name })
      return
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return
    }
  }
  const a = document.createElement('a')
  a.href = URL.createObjectURL(file)
  a.download = file.name
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    URL.revokeObjectURL(a.href)
    a.remove()
  }, 1000)
}

/** Scarica e salva in un passo (per i pulsanti "Scarica"). */
export async function scaricaESalva(url: string): Promise<void> {
  await salvaFile(await scaricaFile(url))
}
