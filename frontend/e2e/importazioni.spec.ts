import { expect, test, type Page } from '@playwright/test'

/**
 * Import tracciati (utente di staff). Richiedono lo stack di sviluppo e:
 * - PLANCIA_E2E_STAFF_EMAIL / PLANCIA_E2E_STAFF_PASSWORD: Admin, Segreteria o Incaricato EG;
 * - PLANCIA_E2E_IMPORT_LOG: id di un log squadriglie con almeno una riga da riconciliare
 *   e una scartata (facoltativo: senza, si salta il test del dettaglio);
 * - PLANCIA_E2E_SOCIO_CAPO: testo che trova un Socio capo nella ricerca (es. un cognome).
 * Gli screenshot finiscono in PLANCIA_E2E_SCREENSHOT (cartella), se impostata.
 */
const email = process.env.PLANCIA_E2E_STAFF_EMAIL
const password = process.env.PLANCIA_E2E_STAFF_PASSWORD
const logId = process.env.PLANCIA_E2E_IMPORT_LOG
const ricercaCapo = process.env.PLANCIA_E2E_SOCIO_CAPO
const cartellaScreenshot = process.env.PLANCIA_E2E_SCREENSHOT

async function accedi(page: Page): Promise<void> {
  await page.goto('/accesso')
  await page.getByLabel('Email').fill(email!)
  await page.getByLabel('Password', { exact: true }).fill(password!)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()
}

async function foto(page: Page, nome: string, progetto: string): Promise<void> {
  if (cartellaScreenshot) await page.screenshot({ path: `${cartellaScreenshot}/${nome}-${progetto}.png`, fullPage: true })
}

test.describe('importazioni', () => {
  test.skip(!email || !password, 'credenziali di staff non impostate')

  test.beforeEach(async ({ page }) => {
    await accedi(page)
  })

  test('lancio: schede dei tracciati, controllo estensione, storico filtrabile', async ({ page }, info) => {
    await page.goto('/import')
    await expect(page.getByRole('heading', { name: 'Import tracciati' })).toBeVisible()
    const capi = page.getByRole('region', { name: /1\. Capi/ })
    await expect(capi).toBeVisible()
    await expect(page.getByRole('region', { name: /Squadriglie iscritte/ }).getByLabel(/Edizione/)).toBeVisible()

    // File con estensione sbagliata: errore immediato, nessun invio
    await capi.getByLabel('File .csv').setInputFiles({ name: 'capi.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('x') })
    await expect(capi.getByText('Il file deve essere in formato .csv.')).toBeVisible()
    // Squadriglie senza edizione: errore lato client
    const sq = page.getByRole('region', { name: /Squadriglie iscritte/ })
    await sq.getByLabel('File .csv').setInputFiles({ name: 'sq.csv', mimeType: 'text/csv', buffer: Buffer.from('a;b\n') })
    await sq.getByRole('button', { name: /Importa/ }).click()
    await expect(sq.getByText("Seleziona un'edizione per l'import squadriglie iscritte.")).toBeVisible()

    await expect(page.getByRole('heading', { name: 'Storico import' })).toBeVisible()
    await page.getByLabel('Tipo').selectOption('coca')
    await expect(page).toHaveURL(/tipo=coca/)
    await foto(page, 'import', info.project.name)
  })

  test('dettaglio: riconciliazione con selettore Socio, scarti, CSV', async ({ page }, info) => {
    test.skip(!logId || !ricercaCapo, 'log di prova o socio capo non impostati')
    await page.goto(`/import/${logId}`)
    await expect(page.getByRole('heading', { name: /Import Squadriglie iscritte del/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: /Righe scartate/ })).toBeVisible()
    await foto(page, 'import-dettaglio', info.project.name)

    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Scarica CSV' }).click()
    expect((await download).suggestedFilename()).toMatch(/^scarti_import_\d+\.csv$/)

    const riga = page.getByRole('article').first()
    const prima = await page.getByRole('article').count()
    const campo = riga.getByRole('combobox', { name: 'Seleziona il Capo Reparto' })
    await campo.fill(ricercaCapo!)
    await riga.getByRole('option').first().click()
    await riga.getByRole('button', { name: /Associa/ }).click()
    await expect(page.getByText(/riconciliata con/)).toBeVisible()
    await expect(page.getByRole('article')).toHaveCount(prima - 1)
  })
})
