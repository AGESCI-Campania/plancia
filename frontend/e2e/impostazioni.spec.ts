import { expect, test, type Page } from '@playwright/test'

/**
 * Impostazioni, pagine statiche e aggiornamenti del server. I flussi da Admin richiedono un
 * utente Admin di prova (PLANCIA_E2E_ADMIN_EMAIL / PLANCIA_E2E_ADMIN_PASSWORD) e, per
 * l'aggiornamento, una release più recente nota al server (ReleaseGitHub). Con
 * PLANCIA_E2E_SCREENSHOT=<cartella> salva le schermate delle pagine principali.
 */
const email = process.env.PLANCIA_E2E_ADMIN_EMAIL
const password = process.env.PLANCIA_E2E_ADMIN_PASSWORD
const cartellaScreenshot = process.env.PLANCIA_E2E_SCREENSHOT

async function accedi(page: Page): Promise<void> {
  await page.goto('/accesso')
  await page.getByLabel('Email').fill(email!)
  await page.getByLabel('Password', { exact: true }).fill(password!)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()
}

async function schermata(page: Page, nome: string): Promise<void> {
  if (!cartellaScreenshot) return
  await page.screenshot({ path: `${cartellaScreenshot}/${nome}-${test.info().project.name}.png`, fullPage: true })
}

/** Conferma la finestra di `conferma()` con il pulsante indicato. */
async function confermaDialogo(page: Page, pulsante: string | RegExp): Promise<void> {
  // (la sidebar e l'eventuale modale "Aggiornamento disponibile" sono anch'esse <dialog>)
  const bottone = page.getByRole('dialog').getByRole('button', { name: pulsante, exact: typeof pulsante === 'string' })
  await expect(bottone).toBeVisible()
  await bottone.click()
}

test('la pagina pubblica della privacy si apre senza login', async ({ page }) => {
  await page.goto('/pagine/privacy')
  await expect(page).toHaveURL(/\/pagine\/privacy$/)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await schermata(page, 'pagina-privacy')
})

test.describe('da Admin', () => {
  test.skip(!email || !password, 'credenziali Admin di prova non impostate')
  test.describe.configure({ mode: 'serial' })

  test('schede delle impostazioni e salvataggio dell’identità', async ({ page }) => {
    await accedi(page)
    await page.goto('/impostazioni')
    await expect(page.getByRole('heading', { name: 'Impostazioni della piattaforma' })).toBeVisible()
    const sottotitolo = page.getByRole('textbox', { name: 'Sottotitolo', exact: true })
    await sottotitolo.fill('Guidoncini Verdi - AGESCI Campania')
    await page.getByRole('button', { name: 'Salva identità' }).click()
    await expect(page.getByText('Identità salvata.')).toBeVisible()
    await schermata(page, 'impostazioni-generale')

    await page.getByRole('link', { name: 'Posta elettronica' }).click()
    await expect(page).toHaveURL(/\/impostazioni\/email$/)
    await expect(page.getByLabel('SMTP password')).toHaveValue('')
    await schermata(page, 'impostazioni-email')

    // destinazione della callback Gmail OAuth: avviso e URL ripulito
    await page.goto('/impostazioni/email?esito=errore&messaggio=Prova%20callback')
    await expect(page.getByText('Prova callback')).toBeVisible()
    await expect(page).toHaveURL(/\/impostazioni\/email$/)

    await page.goto('/impostazioni/sistema')
    await page.getByLabel('Messaggio di manutenzione').fill('Torniamo presto')
    await page.getByRole('button', { name: 'Salva stato e diagnostica' }).click()
    await expect(page.getByText('Stato e diagnostica salvati.')).toBeVisible()
    await schermata(page, 'impostazioni-sistema')
  })

  test('editor dei template email: segnaposto, salvataggio ed eliminazione', async ({ page }) => {
    await accedi(page)
    await page.goto('/impostazioni/template-email')
    await expect(page.getByText('invito_pgv')).toBeVisible()
    await page.goto('/impostazioni/mail/invito_pgv')
    await page.getByLabel('Oggetto email').fill('Invito alla Pattuglia GV')
    await page.locator('.ProseMirror').click()
    await page.keyboard.type('Ciao ')
    await page.getByRole('button', { name: '{{ nome }}' }).click()
    await page.getByRole('button', { name: 'Grassetto' }).click()
    await expect(page.locator('.ProseMirror')).toBeFocused()
    await page.keyboard.type(' benvenuto')
    await page.getByRole('button', { name: 'HTML', exact: true }).click()
    await expect(page.getByRole('button', { name: 'HTML', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await expect(page.locator('textarea')).toHaveValue(/Ciao \{\{ nome \}\}.*<strong>.*benvenuto<\/strong>/)
    await schermata(page, 'template-email')
    await page.getByRole('button', { name: 'Salva template' }).click()
    await expect(page.getByText('Template salvato.')).toBeVisible()

    await page.getByRole('button', { name: 'Elimina (ripristina predefinito)' }).click()
    await confermaDialogo(page, 'Elimina')
    await expect(page).toHaveURL(/\/impostazioni\/template-email$/)
  })

  test('aggiornamento del server: richiesta, monitoraggio e annullamento', async ({ page }) => {
    await accedi(page)
    await page.goto('/impostazioni/aggiornamenti')
    await expect(page.getByText('Versione installata')).toBeVisible()
    // una richiesta rimasta aperta da un'esecuzione precedente si annulla prima
    const annullaVecchia = page.getByRole('button', { name: 'Annulla la richiesta' })
    if (await annullaVecchia.isVisible()) {
      await annullaVecchia.click()
      await confermaDialogo(page, 'Annulla la richiesta')
      await expect(page.getByText('Richiesta di aggiornamento annullata.')).toBeVisible()
    }
    // le note markdown sono rese senza HTML arbitrario
    await expect(page.locator('.impostazioni-note script')).toHaveCount(0)
    const aggiorna = page.getByRole('button', { name: /^Aggiorna a v/ })
    test.skip(!(await aggiorna.isVisible()), 'nessuna release più recente nota al server')
    await schermata(page, 'aggiornamenti')
    await aggiorna.click()
    await confermaDialogo(page, /^Aggiorna a v/)
    await expect(page.getByText(/richiesto: il server lo avvierà a breve/)).toBeVisible()
    await expect(page.getByRole('heading', { name: /^Aggiornamento da v.* a v/ })).toBeVisible()
    await page.getByRole('button', { name: 'Annulla la richiesta' }).click()
    await confermaDialogo(page, 'Annulla la richiesta')
    await expect(page.getByText('Richiesta di aggiornamento annullata.')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Storico degli aggiornamenti' })).toBeVisible()
    await expect(page.getByText('Annullato').first()).toBeVisible()
  })

  test('log export con traceback e cache PDF', async ({ page }) => {
    await accedi(page)
    await page.goto('/impostazioni/log-export')
    await expect(page.getByRole('heading', { name: 'Log generazione PDF / Excel' })).toBeVisible()
    const traceback = page.getByRole('button', { name: /^Traceback del/ }).first()
    if (await traceback.isVisible()) {
      await traceback.click()
      const finestra = page.getByRole('dialog', { name: /^Traceback/ })
      await expect(finestra).toContainText('ValueError')
      await finestra.getByRole('button', { name: 'Chiudi' }).click()
    }
    await schermata(page, 'log-export')
    await page.goto('/impostazioni/cache-pdf')
    await expect(page.getByRole('heading', { name: "Genera tutti i PDF di un'edizione" })).toBeVisible()
    await schermata(page, 'cache-pdf')
    await page.goto('/impostazioni/drive')
    await expect(page.getByRole('heading', { name: 'Account collegati' })).toBeVisible()
  })
})
