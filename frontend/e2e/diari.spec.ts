import { expect, test, type Page } from '@playwright/test'

/**
 * Flussi del dominio diari: elenco con filtri nella query string, dettaglio, cambio del
 * Capo Squadriglia, viewer PDF e cambio del Capo Reparto per reparto. Richiedono dati di
 * prova nel DB di sviluppo:
 * - PLANCIA_E2E_CRP_EMAIL / PLANCIA_E2E_PASSWORD: Capo Reparto con almeno un diario in
 *   compilazione (PLANCIA_E2E_DIARIO_ID) e due ragazzi dello stesso gruppo
 *   (PLANCIA_E2E_GRUPPO, testo di ricerca dei soci);
 * - PLANCIA_E2E_ADMIN_EMAIL: Admin con TOTP (codice di bypass di sviluppo `000000`) e
 *   PLANCIA_E2E_DIARIO_INVIATO_ID, un diario già inviato (PDF), PLANCIA_E2E_REPARTO_ID.
 */
const password = process.env.PLANCIA_E2E_PASSWORD
const crp = process.env.PLANCIA_E2E_CRP_EMAIL
const admin = process.env.PLANCIA_E2E_ADMIN_EMAIL
const diarioId = process.env.PLANCIA_E2E_DIARIO_ID
const diarioInviatoId = process.env.PLANCIA_E2E_DIARIO_INVIATO_ID
const repartoId = process.env.PLANCIA_E2E_REPARTO_ID
const gruppo = process.env.PLANCIA_E2E_GRUPPO ?? ''

async function accedi(page: Page, email: string): Promise<void> {
  await page.goto('/accesso')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password!)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  const mfa = page.getByRole('heading', { name: 'Verifica in due passaggi' })
  const home = page.getByRole('heading', { name: /Benvenuto/ })
  await expect(mfa.or(home)).toBeVisible()
  if (await mfa.isVisible()) {
    await page.getByLabel('Codice').fill('000000')
    await page.getByRole('button', { name: 'Verifica' }).click()
    await expect(home).toBeVisible()
  }
}

test.describe('Capo Reparto', () => {
  test.skip(!crp || !password || !diarioId, 'utente Capo Reparto di prova non impostato')

  test('elenco: filtri sincronizzati con la query string', async ({ page }) => {
    await accedi(page, crp!)
    await page.goto('/diari')
    await expect(page.getByRole('heading', { name: 'Diari di bordo' })).toBeVisible()
    await expect(page.getByText(/\d+ diar[io]/).first()).toBeVisible()

    const filtri = page.getByRole('button', { name: /Filtri/ })
    if (await filtri.isVisible()) await filtri.click()
    await page.getByLabel('Tipo').selectOption('nuovo')
    await expect(page).toHaveURL(/tipo=nuovo/)
    await page.getByRole('search').getByText('In compilazione').click()
    await expect(page).toHaveURL(/stato=in_compilazione/)
    await page.getByLabel('Cerca').fill('zzzz-nessuno')
    await expect(page).toHaveURL(/q=zzzz-nessuno/)
    await expect(page.getByText('Nessun diario corrisponde ai filtri.')).toBeVisible()
    await page.getByRole('button', { name: 'Azzera filtri' }).click()
    await expect(page).toHaveURL(/\/diari$/)

    // La query string ricarica gli stessi filtri (link condivisibile)
    await page.goto('/diari?tipo=rinnovo')
    if (await filtri.isVisible()) await filtri.click()
    await expect(page.getByLabel('Tipo')).toHaveValue('rinnovo')
  })

  test('dettaglio e cambio del Capo Squadriglia', async ({ page }) => {
    await accedi(page, crp!)
    await page.goto(`/diari/${diarioId}`)
    await expect(page.getByRole('heading', { name: 'Stato della compilazione' })).toBeVisible()
    await expect(page.getByRole('link', { name: /Modulo 1\s*Anagrafica/ })).toHaveAttribute(
      'href',
      `/diari/${diarioId}/anagrafica`,
    )
    await expect(page.getByRole('heading', { name: /Modulo 6/ })).toBeVisible()
    await expect(page.getByText('Valutazione', { exact: true })).toHaveCount(0)

    await page.getByRole('button', { name: 'Cambia Capo Squadriglia' }).click()
    const finestra = page.getByRole('dialog', { name: 'Cambia Capo Squadriglia' })
    await expect(finestra).toBeVisible()
    await finestra.getByRole('combobox', { name: 'Nuovo Capo Squadriglia' }).fill(gruppo || 'Test')
    const opzione = finestra.getByRole('option').first()
    await expect(opzione).toBeVisible()
    await opzione.click()
    await finestra.getByRole('button', { name: 'Conferma cambio' }).click()
    await expect(finestra).toBeHidden()
    await expect(page.getByText(/Capo Squadriglia aggiornato/)).toBeVisible()
  })
})

test.describe('Admin', () => {
  test.skip(!admin || !password || !diarioInviatoId, 'utente Admin di prova non impostato')

  test('viewer del PDF: anteprima o stato di generazione', async ({ page }) => {
    await accedi(page, admin!)
    await page.goto(`/diari/${diarioInviatoId}`)
    await page.getByRole('link', { name: 'PDF del diario' }).click()
    await expect(page).toHaveURL(new RegExp(`/diari/${diarioInviatoId}/pdf$`))
    const scarica = page.getByRole('button', { name: 'Scarica' })
    const genera = page.getByRole('button', { name: 'Genera il PDF' })
    await expect(page.locator('iframe').or(genera).or(page.getByText('File pronto.'))).toBeVisible({
      timeout: 30_000,
    })
    if (!(await genera.isVisible())) await expect(scarica).toBeEnabled()
  })

  test('cambio del Capo Reparto per reparto', async ({ page }) => {
    test.skip(!repartoId, 'reparto di prova non impostato')
    await accedi(page, admin!)
    await page.goto(`/reparti/${repartoId}/cambia-capo-reparto`)
    await expect(page.getByRole('heading', { name: /Cambia Capo Reparto/ })).toBeVisible()
    const campo = page.getByRole('combobox', { name: 'Nuovo Capo Reparto' })
    if (await campo.isVisible()) {
      await campo.fill(gruppo || 'Test')
      await expect(page.getByRole('option').first()).toBeVisible()
      await page.getByRole('option').first().click()
      await page.getByRole('button', { name: 'Conferma cambio per tutti i diari' }).click()
      await page.getByRole('dialog').getByRole('button', { name: 'Conferma cambio' }).click()
      await expect(page).toHaveURL(/\/diari$/)
      await expect(page.getByText(/Capo Reparto aggiornato/)).toBeVisible()
    } else {
      await expect(page.getByText('Nessun diario non ancora inviato')).toBeVisible()
    }
  })
})
