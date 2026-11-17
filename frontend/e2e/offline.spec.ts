import { expect, test } from '@playwright/test'

// Compilazione offline (Fase 5): richiede un Capo Squadriglia con un diario in compilazione
// (PLANCIA_E2E_MODULI_CSQ_EMAIL, PLANCIA_E2E_MODULI_PASSWORD, PLANCIA_E2E_MODULI_DIARIO).
const email = process.env.PLANCIA_E2E_MODULI_CSQ_EMAIL
const password = process.env.PLANCIA_E2E_MODULI_PASSWORD
const diario = process.env.PLANCIA_E2E_MODULI_DIARIO

test('modulo compilato offline: resta sul dispositivo e parte alla riconnessione', async ({ page, context }) => {
  test.skip(!email || !password || !diario, 'dati di prova non impostati')
  await page.goto('/accesso')
  await page.getByLabel('Email').fill(email!)
  await page.getByLabel('Password', { exact: true }).fill(password!)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()

  await page.goto(`/diari/${diario}/presentazione`)
  const campo = page.getByLabel('Cosa sappiamo fare')
  await expect(campo).toBeVisible()

  await context.setOffline(true)
  const testo = `Scritto offline ${Date.now()}`
  await campo.fill(testo)
  // Dopo l'autosave la modifica è in coda: l'header la conta
  await expect(page.getByRole('button', { name: /1 da inviare/ })).toBeVisible({ timeout: 15_000 })

  await context.setOffline(false)
  await page.evaluate(() => window.dispatchEvent(new Event('online')))
  await expect(page.getByRole('button', { name: /da inviare/ })).toBeHidden({ timeout: 15_000 })

  await page.reload()
  await expect(page.getByLabel('Cosa sappiamo fare')).toHaveValue(testo)
})
