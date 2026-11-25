import { expect, test } from '@playwright/test'

test('nessun avviso in un browser compatibile', async ({ page }) => {
  await page.goto('/accesso')
  await expect(page.getByRole('heading', { name: 'Accedi a Plancia' })).toBeVisible()
  await expect(page.locator('#avviso-browser')).toHaveCount(0)
})

test('avviso in un browser vecchio, anche se l’app non parte', async ({ page }) => {
  await page.addInitScript(() => {
    CSS.supports = () => false
  })
  await page.route('**/src/main.ts*', (route) => route.abort())
  await page.goto('/accesso')
  await expect(page.locator('#avviso-browser')).toContainText('iOS 18')
  await page.getByRole('button', { name: 'Chiudi' }).click()
  await expect(page.locator('#avviso-browser')).toHaveCount(0)
  await page.reload()
  await expect(page.locator('#avviso-browser')).toHaveCount(0)
})
