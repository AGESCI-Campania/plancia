import { expect, test, type Page } from '@playwright/test'

/**
 * Utenti e nomine, profilo, inviti, helpdesk. Richiedono lo stack di sviluppo con dati di prova:
 * - PLANCIA_E2E_STAFF_EMAIL / PLANCIA_E2E_PASSWORD: un Admin (può impersonare);
 * - PLANCIA_E2E_CRP_EMAIL: un Capo Reparto con almeno un diario dell'edizione attiva e un invito
 *   al suo Capo Squadriglia; PLANCIA_E2E_CRP_NOME: il suo nome come lo mostra Plancia
 *   (cognome e nome, es. "Reparto Carlo");
 * - PLANCIA_E2E_SOCIO_CAPO: cognome di un Socio capo per l'autocompletamento.
 */
const staff = process.env.PLANCIA_E2E_STAFF_EMAIL
const crp = process.env.PLANCIA_E2E_CRP_EMAIL
const crpNome = process.env.PLANCIA_E2E_CRP_NOME
const password = process.env.PLANCIA_E2E_PASSWORD
const socioCapo = process.env.PLANCIA_E2E_SOCIO_CAPO

type Cookie = Awaited<ReturnType<ReturnType<Page['context']>['cookies']>>[number]
// Cookie di sessione per utente: allauth limita i login ripetuti, si accede una volta sola.
const sessioni = new Map<string, Cookie[]>()

async function accedi(page: Page, email: string, { riusa = true } = {}): Promise<void> {
  const salvati = riusa ? sessioni.get(email) : undefined
  if (salvati) {
    await page.context().addCookies(salvati)
    await page.goto('/')
  } else {
    await page.goto('/accesso')
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password', { exact: true }).fill(password!)
    await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  }
  await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()
  if (riusa && !salvati) sessioni.set(email, await page.context().cookies())
}

/** Conferma nella finestra di `conferma()`. */
async function confermaDialogo(page: Page, pulsante: string): Promise<void> {
  const dialogo = page.locator('dialog[open]') // su desktop anche la sidebar è un <dialog>
  await expect(dialogo).toBeVisible()
  await dialogo.getByRole('button', { name: pulsante, exact: true }).click()
}

test.describe('staff', () => {
  test.skip(!staff || !password || !crpNome, 'utente staff di prova non impostato')

  test('elenco utenti con ricerca, nomina e revoca di un ruolo', async ({ page }) => {
    await accedi(page, staff!)
    await page.goto('/utenti')
    await expect(page.getByRole('heading', { name: 'Utenti', exact: true })).toBeVisible()
    await page.getByLabel('Cerca').fill(crpNome!.split(' ')[0]!)
    await expect(page).toHaveURL(/q=/)
    await page.getByRole('link', { name: crpNome!, exact: true }).click()
    await expect(page.getByRole('heading', { name: crpNome! })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Storico nomine' })).toBeVisible()

    await page.getByLabel('Ruolo', { exact: true }).selectOption({ label: 'Membro Pattuglia Guidoncini Verdi' })
    await page.getByRole('button', { name: 'Conferma nomina' }).click()
    await expect(page.getByText(/Ruolo Membro Pattuglia Guidoncini Verdi assegnato/)).toBeVisible()

    await page.getByRole('button', { name: 'Revoca la nomina Membro Pattuglia Guidoncini Verdi' }).first().click()
    await confermaDialogo(page, 'Revoca')
    await expect(page.getByText('Ruolo Membro Pattuglia Guidoncini Verdi revocato.')).toBeVisible()
  })

  test('nuovo utente di staff e autocompletamento del Socio', async ({ page }) => {
    await accedi(page, staff!)
    await page.goto('/utenti/nuovo')
    const email = `staff.${Date.now()}@e2e.it`
    await page.getByLabel('Nome', { exact: true }).fill('Prova')
    await page.getByLabel('Cognome').fill('Staff')
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Ruolo').selectOption({ index: 1 })
    await page.getByRole('button', { name: /Crea utente/ }).click()
    await expect(page.getByText(new RegExp(`Utente ${email.replace('.', '\\.')} creato`))).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Prova Staff' })).toBeVisible()

    test.skip(!socioCapo, 'socio capo di prova non impostato')
    await page.goto('/utenti/nuovo?tipo=socio')
    const cerca = page.getByRole('combobox', { name: 'Socio (capo)' })
    await cerca.fill(socioCapo!.slice(0, 4))
    const opzione = page.getByRole('option', { name: new RegExp(socioCapo!) })
    await expect(opzione).toBeVisible()
    await cerca.press('Enter')
    await expect(cerca).toHaveValue(new RegExp(socioCapo!))
    await expect(page.getByRole('button', { name: 'Togli il socio scelto' })).toBeVisible()
  })

  test('gestione inviti: contatori, stato di consegna, filtri', async ({ page }) => {
    await accedi(page, staff!)
    await page.goto('/gestione/inviti')
    await expect(page.getByRole('heading', { name: 'Gestione inviti' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Capi Reparto' })).toBeVisible()
    await expect(page.getByRole('button', { name: /Invia inviti ai Capi Squadriglia/ })).toBeVisible()
    await expect(page.getByRole('cell', { name: new RegExp(crpNome!) }).first()).toBeVisible()
    await page.getByLabel('Cerca Capo Reparto o Capo Squadriglia').fill('zzzz-nessuno')
    await expect(page.getByText('Nessuna riga corrisponde ai filtri selezionati.')).toBeVisible()
    await page.getByRole('button', { name: 'Azzera filtri' }).click()
    await expect(page.getByRole('button', { name: /Invia gli inviti mancanti di/ }).first()).toBeVisible()
  })

  test('helpdesk: apertura, risposta e chiusura di un ticket', async ({ page }) => {
    await accedi(page, staff!)
    await page.goto('/helpdesk')
    await page.getByRole('link', { name: 'Nuovo ticket' }).click()
    await page.getByRole('button', { name: 'Apri ticket' }).click()
    await expect(page.getByText('Scrivi l’oggetto.')).toBeVisible()
    const oggetto = `Prova e2e ${Date.now()}`
    await page.getByLabel('Oggetto').fill(oggetto)
    await page.getByLabel('Categoria').selectOption('tecnico')
    await page.getByLabel('Descrizione').fill('Riga uno\nRiga due')
    await page.getByRole('button', { name: 'Apri ticket' }).click()
    await expect(page.getByRole('heading', { name: new RegExp(oggetto) })).toBeVisible()

    await page.getByLabel('La tua risposta').fill('Ci pensiamo noi.')
    await page.getByRole('button', { name: 'Rispondi' }).click()
    await expect(page.getByText('Ci pensiamo noi.')).toBeVisible()
    await expect(page.getByText('In lavorazione', { exact: true })).toBeVisible()

    await page.getByRole('button', { name: 'Chiudi ticket' }).click()
    await confermaDialogo(page, 'Chiudi ticket')
    await expect(page.getByText(/Ticket chiuso il/)).toBeVisible()
    await expect(page.getByLabel('La tua risposta')).toHaveCount(0)
  })

  test('impersonazione e ritorno al proprio account', async ({ page }) => {
    // Sessione propria: l'impersonazione ruota la chiave di sessione.
    await accedi(page, staff!, { riusa: false })
    await page.goto('/utenti')
    await page.getByLabel('Cerca').fill(crpNome!.split(' ')[0]!)
    await page.getByRole('link', { name: crpNome!, exact: true }).click()
    await page.getByRole('button', { name: 'Impersona utente' }).click()
    await confermaDialogo(page, 'Impersona')
    await expect(page.getByText(`Stai operando come ${crpNome}`)).toBeVisible()
    await page.getByRole('button', { name: 'Torna al tuo account' }).click()
    await expect(page.getByText(/Stai operando come/)).toHaveCount(0)
    await expect(page.getByRole('heading', { name: /Benvenuto/ })).toBeVisible()
  })
})

test.describe('Capo Reparto', () => {
  test.skip(!crp || !password, 'Capo Reparto di prova non impostato')

  test('profilo con nomine, accessi e sessioni', async ({ page }) => {
    await accedi(page, crp!)
    await page.goto('/profilo')
    await expect(page.getByRole('heading', { name: 'Il mio profilo' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Storico nomine' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Ultimi accessi' })).toBeVisible()
    await expect(page.getByText('Questa sessione')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Modifica email' })).toHaveCount(0)
    await page.getByRole('link', { name: 'Password e sicurezza' }).first().click()
    await expect(page).toHaveURL(/\/profilo\/sicurezza$/)
  })

  test('inviti dei propri Capi Squadriglia e reinvio', async ({ page }) => {
    await accedi(page, crp!)
    await page.goto('/inviti')
    await expect(page.getByRole('heading', { name: 'Inviti Capi Squadriglia' })).toBeVisible()
    const reinvia = page.getByRole('button', { name: /^Reinvia a / }).first()
    await expect(reinvia).toBeVisible()
    await reinvia.click()
    await confermaDialogo(page, 'Reinvia')
    await expect(page.getByText(/Invito reinviato/)).toBeVisible()
  })

  test('helpdesk: solo i propri ticket, senza presa in carico', async ({ page }) => {
    await accedi(page, crp!)
    await page.goto('/helpdesk')
    await expect(page.getByText('Le tue richieste di assistenza', { exact: false })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Assegnato a' })).toHaveCount(0)
    const primo = page.getByRole('link', { name: /#\d+/ }).first()
    if (await primo.count()) {
      await primo.click()
      await expect(page.getByRole('button', { name: 'Prendi in carico' })).toHaveCount(0)
    }
  })
})
