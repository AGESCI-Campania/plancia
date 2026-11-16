import { expect, test, type Page } from '@playwright/test'

/*
 * Home, edizioni e valutazioni. Richiedono un DB di prova con un'edizione aperta e diari:
 *   PLANCIA_E2E_STAFF_EMAIL / PLANCIA_E2E_STAFF_PASSWORD  Incaricato EG (o Admin)
 *   PLANCIA_E2E_CSQ_EMAIL / PLANCIA_E2E_CSQ_PASSWORD      Capo Squadriglia
 *   PLANCIA_E2E_DIARIO_INVIATO                            id di un diario inviato
 * Senza le variabili i test si saltano.
 */
const staff = { email: process.env.PLANCIA_E2E_STAFF_EMAIL, password: process.env.PLANCIA_E2E_STAFF_PASSWORD }
const csq = { email: process.env.PLANCIA_E2E_CSQ_EMAIL, password: process.env.PLANCIA_E2E_CSQ_PASSWORD }
const diarioInviato = process.env.PLANCIA_E2E_DIARIO_INVIATO

async function accedi(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/accesso')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()
}

test.describe('staff', () => {
  test.skip(!staff.email || !staff.password, 'credenziali staff non impostate')

  test.beforeEach(async ({ page }) => {
    await accedi(page, staff.email!, staff.password!)
  })

  test("la home mostra l'edizione attiva con avanzamento e diari filtrabili", async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Guidoncini Verdi \d{4}/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Avanzamento diari' })).toBeVisible()
    const tabella = page.getByRole('table')
    await expect(tabella.getByRole('row').nth(1)).toBeVisible()
    await page.getByLabel('Stato', { exact: true }).selectOption('inviato')
    await expect(tabella.getByText('Inviato').first()).toBeVisible()
    await expect(tabella.getByText('Non iniziato')).toHaveCount(0)
    await page.getByRole('button', { name: 'Azzera filtri' }).click()
    await expect(page.getByLabel('Stato', { exact: true })).toHaveValue('')
  })

  test('dettaglio edizione: azioni di gestione, dilazioni e Drive', async ({ page }) => {
    await page.getByRole('link', { name: 'Gestisci edizione' }).click()
    await expect(page).toHaveURL(/\/edizioni\/\d+$/)
    const azioni = page.getByRole('toolbar', { name: "Azioni sull'edizione" })
    await expect(azioni.getByRole('button', { name: 'Esiti Excel' })).toBeVisible()
    await azioni.getByRole('button', { name: /Esporta diari/ }).click()
    await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('heading', { name: 'Dilazioni' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Google Drive' })).toBeVisible()
    // Concessione di una dilazione: la finestra elenca solo i diari non ancora inviati
    await page.getByRole('button', { name: 'Concedi dilazione' }).click()
    const dialogo = page.getByRole('dialog', { name: 'Concedi una dilazione' })
    await expect(dialogo.getByLabel('Diario')).toBeVisible()
    await dialogo.getByRole('button', { name: 'Annulla' }).click()
  })

  test('ritorno dalla callback di Drive con esito', async ({ page }) => {
    await page.getByRole('link', { name: 'Gestisci edizione' }).click()
    await expect(page).toHaveURL(/\/edizioni\/\d+$/)
    const url = page.url()
    await page.goto(`${url}?drive=errore&messaggio=Accesso%20negato`)
    await expect(page.getByRole('status').filter({ hasText: 'Accesso negato' })).toBeVisible()
    await expect(page).toHaveURL(/\/edizioni\/\d+$/)
  })

  test('nuova edizione dal form', async ({ page }) => {
    const anno = String(2100 + Math.floor(Math.random() * 800))
    await page.goto('/edizioni/nuova')
    await page.getByLabel('Anno').fill(anno)
    await page.getByLabel('Inizio evento').fill('2030-05-12')
    await page.getByLabel('Fine evento').fill('2030-05-10')
    await page.getByRole('button', { name: 'Salva edizione' }).click()
    await expect(page.getByText('La data di fine non può precedere quella di inizio.')).toBeVisible()
    await page.getByLabel('Fine evento').fill('2030-05-14')
    await page.getByRole('button', { name: 'Salva edizione' }).click()
    await expect(page).toHaveURL(/\/edizioni$/)
    await expect(page.getByRole('heading', { name: `Guidoncini Verdi ${anno}` })).toBeVisible()
  })

  test('valutazione diretta di un diario inviato', async ({ page }) => {
    test.skip(!diarioInviato, 'diario di prova non impostato')
    await page.goto(`/diari/${diarioInviato}/valutazione`)
    await expect(page.getByRole('heading', { name: 'Stato valutazione' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Assegnazioni Pattuglia GV' })).toBeVisible()
    const valuta = page.getByRole('heading', { name: 'Valuta direttamente' })
    if (await valuta.isVisible()) {
      await page.getByLabel('Esito').selectOption('approvata')
      await page.getByRole('button', { name: 'Conferma valutazione' }).click()
      await expect(page.getByRole('status').filter({ hasText: 'Valutazione registrata.' })).toBeVisible()
    }
    // Dopo la valutazione: esito modificabile fino alla pubblicazione, pulsante Pubblica
    await expect(page.getByRole('heading', { name: 'Modifica esito' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Pubblica esito' })).toBeVisible()
  })
})

// Assegnazione alla Pattuglia GV, proposta e conferma dell'Incaricato (PLANCIA_E2E_PGV_*,
// PLANCIA_E2E_DIARI_PGV: due diari inviati e mai valutati, uno per progetto desktop/iphone,
// separati da virgola; il flusso li porta ad "approvato", quindi servono dati nuovi a ogni giro).
const pgv = { email: process.env.PLANCIA_E2E_PGV_EMAIL, password: process.env.PLANCIA_E2E_PGV_PASSWORD }
const diariPgv = (process.env.PLANCIA_E2E_DIARI_PGV ?? '').split(',').filter(Boolean)

test.describe('Pattuglia GV', () => {
  test.skip(!staff.email || !pgv.email || !pgv.password || !diariPgv.length, 'Pattuglia GV di prova non impostata')

  test("assegnazione, proposta e conferma dell'Incaricato", async ({ page }, info) => {
    const diarioPgv = diariPgv[info.project.name === 'iphone' ? 1 : 0] ?? diariPgv[0]
    await accedi(page, staff.email!, staff.password!)
    await page.goto(`/diari/${diarioPgv}/valutazione`)
    const ricerca = page.getByRole('combobox', { name: 'Membro della Pattuglia GV' })
    await ricerca.fill('Pattuglia')
    await page.getByRole('option', { name: /Pattuglia/ }).first().click()
    await page.getByRole('button', { name: 'Assegna', exact: true }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Diario assegnato a' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Assegnazioni Pattuglia GV' }).getByRole('listitem')).not.toHaveCount(0)

    await page.context().clearCookies()
    await accedi(page, pgv.email!, pgv.password!)
    await page.goto(`/diari/${diarioPgv}/valutazione`)
    await expect(page.getByRole('heading', { name: 'Proponi valutazione' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Assegnazioni Pattuglia GV' })).toHaveCount(0)
    await page.getByLabel('Esito').selectOption('approvata')
    await page.getByRole('button', { name: 'Proponi', exact: true }).click()
    await expect(page.getByText("in attesa di conferma da parte di un Incaricato EG")).toBeVisible()

    await page.context().clearCookies()
    await accedi(page, staff.email!, staff.password!)
    await page.goto(`/diari/${diarioPgv}/valutazione`)
    await expect(page.getByRole('heading', { name: /Proposta della Pattuglia GV in attesa/ })).toBeVisible()
    await page.getByRole('button', { name: 'Conferma proposta' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Proposta confermata.' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Pubblica esito' })).toBeVisible()
  })
})

test.describe('Capo Squadriglia', () => {
  test.skip(!csq.email || !csq.password || !diarioInviato, 'credenziali o diario non impostati')

  test('non vede mai la valutazione', async ({ page }) => {
    await accedi(page, csq.email!, csq.password!)
    await page.goto(`/diari/${diarioInviato}/valutazione`)
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Stato valutazione' })).toHaveCount(0)
  })
})
