import { expect, test } from '@playwright/test'

// Richiede lo stack di sviluppo: Django su :8000 (con l'utente di prova creato dal seed) e Vite.
test('chi non è autenticato arriva alla pagina di accesso', async ({ page }) => {
  await page.goto('/diari')
  await expect(page).toHaveURL(/\/accesso\?next=(%2F|\/)diari/)
  await expect(page.getByRole('heading', { name: 'Accedi a Plancia' })).toBeVisible()
})

test('il footer mostra la versione dell’app', async ({ page }) => {
  await page.goto('/accesso')
  await expect(page.getByText(/App v\d+\.\d+\.\d+/)).toBeVisible()
})

// Login reale: richiede un utente di prova (PLANCIA_E2E_EMAIL / PLANCIA_E2E_PASSWORD) nel DB di sviluppo.
test('login con email e password, menu utente e uscita', async ({ page }) => {
  const email = process.env.PLANCIA_E2E_EMAIL
  const password = process.env.PLANCIA_E2E_PASSWORD
  test.skip(!email || !password, 'credenziali di prova non impostate')
  await page.goto('/accesso')
  await page.getByLabel('Email').fill(email!)
  await page.getByLabel('Password', { exact: true }).fill(password!)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()
  // Sotto lg il menu è nel drawer: si apre con il pulsante dell'header
  const apriMenu = page.getByRole('button', { name: 'Apri menu' })
  if (await apriMenu.isVisible()) await apriMenu.click()
  await expect(page.getByRole('link', { name: 'Helpdesk' })).toBeVisible()
})
