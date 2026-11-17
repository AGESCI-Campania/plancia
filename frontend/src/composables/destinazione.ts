/**
 * Dove andare dopo l'accesso (`?next=`): una rotta della SPA oppure una pagina servita da
 * Django (pannello admin, Mailpit, Flower), che va caricata dal browser, non dal router.
 * Solo percorsi interni: niente URL esterni (open redirect).
 */
import type { Router } from 'vue-router'

const PAGINE_DJANGO = /^\/(admin|mailadmin|celery)(\/|$)/

export function destinazioneSicura(next: unknown): string {
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : '/'
}

export async function vaiDopoAccesso(router: Router, next: unknown): Promise<void> {
  const destinazione = destinazioneSicura(next)
  if (PAGINE_DJANGO.test(destinazione)) window.location.assign(destinazione)
  else await router.replace(destinazione)
}
