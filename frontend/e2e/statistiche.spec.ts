import { expect, test, type Page } from '@playwright/test'

/**
 * Dashboard statistiche (utente di staff). Richiede lo stack di sviluppo e
 * PLANCIA_E2E_STAFF_EMAIL / PLANCIA_E2E_STAFF_PASSWORD (Admin, Segreteria o Incaricato EG),
 * con almeno un'edizione e qualche diario. Screenshot in PLANCIA_E2E_SCREENSHOT, se impostata.
 */
const email = process.env.PLANCIA_E2E_STAFF_EMAIL
const password = process.env.PLANCIA_E2E_STAFF_PASSWORD
const cartellaScreenshot = process.env.PLANCIA_E2E_SCREENSHOT

async function accedi(page: Page): Promise<void> {
  await page.goto('/accesso')
  await page.getByLabel('Email').fill(email!)
  await page.getByLabel('Password', { exact: true }).fill(password!)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()
}

test.describe('statistiche', () => {
  test.skip(!email || !password, 'credenziali di staff non impostate')

  test('indicatori, grafici con tabella dati, per zona, cambio edizione', async ({ page }, info) => {
    await accedi(page)
    await page.goto('/statistiche')
    await expect(page.getByRole('heading', { name: 'Statistiche' })).toBeVisible()
    const selettore = page.getByLabel('Edizione', { exact: true })
    await expect(selettore).toBeVisible()
    await expect(page.getByText('Totale diari')).toBeVisible()
    const grafico = page.getByRole('figure', { name: 'Esiti per zona' })
    await expect(grafico).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Per zona' })).toBeVisible()
    await grafico.getByText('Dati del grafico in tabella').click()
    await expect(grafico.getByRole('table', { name: 'Esiti per zona' })).toBeVisible()
    if (cartellaScreenshot) {
      await page.screenshot({ path: `${cartellaScreenshot}/statistiche-${info.project.name}.png`, fullPage: true })
    }

    // Cambio edizione: la scelta finisce nella query string
    const attuale = await selettore.inputValue()
    const valori = await selettore.locator('option').evaluateAll((o) => o.map((x) => (x as HTMLOptionElement).value))
    const altra = valori.find((v) => v !== attuale)
    if (altra) {
      await selettore.selectOption(altra)
      await expect(page).toHaveURL(new RegExp(`edizione=${altra}`))
      await expect(selettore).toHaveValue(altra)
    }
  })
})
