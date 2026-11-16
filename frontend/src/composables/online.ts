import { onScopeDispose, ref, type Ref } from 'vue'

/** `navigator.onLine` reattivo (indicativo: la verità è l'esito delle richieste). */
export function useOnline(): Ref<boolean> {
  const online = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
  const aggiorna = () => (online.value = navigator.onLine)
  window.addEventListener('online', aggiorna)
  window.addEventListener('offline', aggiorna)
  onScopeDispose(() => {
    window.removeEventListener('online', aggiorna)
    window.removeEventListener('offline', aggiorna)
  })
  return online
}
