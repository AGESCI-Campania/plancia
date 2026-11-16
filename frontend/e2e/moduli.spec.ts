import { expect, test, type Page } from '@playwright/test'

/**
 * Moduli del Diario e foto. Richiedono dati di prova nel DB di sviluppo:
 * - PLANCIA_E2E_MODULI_CSQ_EMAIL / PLANCIA_E2E_MODULI_PASSWORD: Capo Squadriglia del diario
 *   PLANCIA_E2E_MODULI_DIARIO (non ancora inviato);
 * - PLANCIA_E2E_MODULI_CRP_EMAIL: Capo Reparto del diario PLANCIA_E2E_MODULI_DIARIO_RELAZIONE
 *   (in stato "Relazione finale").
 * I test modificano gli stessi moduli: eseguirli con `--workers=1`.
 * Con PLANCIA_E2E_SCREENSHOT=<cartella> salvano anche gli screenshot delle pagine.
 */
const csq = process.env.PLANCIA_E2E_MODULI_CSQ_EMAIL
const crp = process.env.PLANCIA_E2E_MODULI_CRP_EMAIL
const password = process.env.PLANCIA_E2E_MODULI_PASSWORD
const diario = process.env.PLANCIA_E2E_MODULI_DIARIO
const diarioRelazione = process.env.PLANCIA_E2E_MODULI_DIARIO_RELAZIONE
const cartellaScreenshot = process.env.PLANCIA_E2E_SCREENSHOT

test.describe.configure({ mode: 'serial' })

async function accedi(page: Page, email: string): Promise<void> {
  await page.goto('/accesso')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password!)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()
}

async function screenshot(page: Page, nome: string, progetto: string): Promise<void> {
  if (cartellaScreenshot) await page.screenshot({ path: `${cartellaScreenshot}/${nome}-${progetto}.png`, fullPage: true })
}

const salvato = (page: Page) => expect(page.getByRole('status').filter({ hasText: /Salvato alle|Tutto salvato/ })).toBeVisible()

// PNG 1×1 per il caricamento delle foto
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)

test.describe('Capo Squadriglia', () => {
  test.skip(!csq || !password || !diario, 'dati di prova dei moduli non impostati')

  test('presentazione: autosave di testo e membri, ritrovati dopo il ricaricamento', async ({ page }, info) => {
    await accedi(page, csq!)
    await page.goto(`/diari/${diario}/presentazione`)
    await expect(page.getByRole('heading', { name: /Presentazione della squadriglia/ })).toBeVisible()
    const testo = `Sappiamo fare nodi (${info.project.name} ${Date.now()})`
    await page.getByLabel('Cosa sappiamo fare').fill(testo)
    await page.getByRole('button', { name: 'Aggiungi membro' }).click()
    const nome = `Membro ${info.project.name}`
    // Il focus va sul primo campo della nuova riga
    await page.keyboard.type(nome)
    await expect(page.getByRole('status').filter({ hasText: /Modifiche da salvare|Salvataggio/ })).toBeVisible()
    await salvato(page)
    await screenshot(page, 'presentazione', info.project.name)

    await page.reload()
    await expect(page.getByLabel('Cosa sappiamo fare')).toHaveValue(testo)
    const campiNome = page.getByLabel('Nome e cognome')
    await expect(campiNome.last()).toHaveValue(nome)
    // Pulizia: tolgo il membro aggiunto (riga salvata → conferma)
    const righe = page.getByRole('listitem').filter({ has: page.getByLabel('Nome e cognome') })
    await righe.last().getByRole('button', { name: /Rimuovi membro/ }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Rimuovi' }).click()
    await salvato(page)
  })

  test('anagrafica: email dei referenti in sola lettura per chi non è staff', async ({ page }, info) => {
    await accedi(page, csq!)
    await page.goto(`/diari/${diario}/anagrafica`)
    await expect(page.getByRole('heading', { name: /Anagrafica/ })).toBeVisible()
    const email = page.getByRole('textbox', { name: /Email/ })
    await expect(email.first()).toHaveAttribute('readonly', '')
    await expect(page.getByText('solo staff').first()).toBeVisible()
    await page.getByRole('textbox', { name: 'Cellulare' }).first().fill('333 1234567')
    await salvato(page)
    await screenshot(page, 'anagrafica', info.project.name)
    // Navigazione tra i moduli con la completezza
    await expect(page.getByRole('navigation', { name: 'Moduli del diario' }).getByRole('link', { name: /Anagrafica/ })).toHaveAttribute('aria-current', 'page')
  })

  test('1ª impresa: posto d’azione e foto (caricamento, anteprima, eliminazione)', async ({ page }, info) => {
    await accedi(page, csq!)
    await page.goto(`/diari/${diario}/imprese/1`)
    await expect(page.getByRole('heading', { name: /1ª impresa/ }).first()).toBeVisible()
    await page.getByLabel('Titolo', { exact: true }).fill(`Costruiamo una zattera ${info.project.name}`)
    await page.getByRole('button', { name: "Aggiungi posto d'azione" }).click()
    await page.keyboard.type('Luca')
    await salvato(page)

    const nomeFoto = `zattera-${info.project.name}-${Date.now()}`
    await page.getByTestId('input-foto-impresa_1').setInputFiles({ name: `${nomeFoto}.png`, mimeType: 'image/png', buffer: PNG })
    const foto = page.getByRole('button', { name: `Apri la foto ${nomeFoto}.jpg` })
    await expect(foto).toBeVisible()
    await screenshot(page, 'impresa', info.project.name)
    await foto.click()
    await expect(page.getByRole('dialog').getByRole('button', { name: 'Scarica' })).toBeVisible()
    await page.getByRole('dialog').getByRole('button', { name: 'Elimina' }).click()
    await page.getByRole('dialog').filter({ hasText: 'Eliminare la foto' }).getByRole('button', { name: 'Elimina' }).click()
    await expect(foto).toHaveCount(0)
  })

  test('conflitto: il modulo salvato altrove si può ricaricare', async ({ page, context }, info) => {
    await accedi(page, csq!)
    const altra = await context.newPage()
    await page.goto(`/diari/${diario}/missione`)
    await altra.goto(`/diari/${diario}/missione`)
    await expect(altra.getByLabel('Titolo', { exact: true })).toBeVisible()

    await page.getByLabel('Titolo', { exact: true }).fill(`Missione A ${info.project.name}`)
    await salvato(page)
    await altra.getByLabel('Titolo', { exact: true }).fill(`Missione B ${info.project.name}`)
    await expect(altra.getByRole('alert').filter({ hasText: 'modificato altrove' })).toBeVisible()
    await screenshot(altra, 'conflitto', info.project.name)
    await altra.getByRole('button', { name: 'Ricarica la versione salvata' }).click()
    await altra.getByRole('dialog').getByRole('button', { name: 'Ricarica' }).click()
    await expect(altra.getByLabel('Titolo', { exact: true })).toHaveValue(`Missione A ${info.project.name}`)
  })

  test('la relazione finale non è accessibile al Capo Squadriglia', async ({ page }) => {
    await accedi(page, csq!)
    await page.goto(`/diari/${diario}/relazione-finale`)
    await expect(page.getByText('non è visibile al Capo Squadriglia')).toBeVisible()
    await expect(page.getByLabel('Sintesi 1ª impresa')).toHaveCount(0)
  })
})

test.describe('Capo Reparto', () => {
  test.skip(!crp || !password || !diarioRelazione, 'dati di prova dei moduli non impostati')

  test('relazione finale: compilazione con autosave', async ({ page }, info) => {
    await accedi(page, crp!)
    await page.goto(`/diari/${diarioRelazione}/relazione-finale`)
    await expect(page.getByRole('heading', { name: /Relazione finale del Capo Reparto/ })).toBeVisible()
    await page.getByLabel('Sintesi 1ª impresa').fill(`Ottimo lavoro (${info.project.name})`)
    await page.getByLabel(/specialità di squadriglia sia stata conquistata/).selectOption('true')
    await salvato(page)
    await page.reload()
    await expect(page.getByLabel(/specialità di squadriglia sia stata conquistata/)).toHaveValue('true')
    await screenshot(page, 'relazione', info.project.name)
  })

  test('moduli del Capo Squadriglia in sola lettura dopo l’invio', async ({ page }) => {
    await accedi(page, crp!)
    await page.goto(`/diari/${diarioRelazione}/imprese/2`)
    await expect(page.getByRole('note').filter({ hasText: 'sola lettura' })).toBeVisible()
    await expect(page.getByLabel('Titolo', { exact: true })).toHaveAttribute('readonly', '')
    await expect(page.getByRole('button', { name: 'Salva ora' })).toHaveCount(0)
  })
})
