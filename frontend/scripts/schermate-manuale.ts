/**
 * Screenshot del manuale d'uso (docs/manuale/screenshots/*.png) contro uno stack locale.
 *
 * Prerequisiti (vedi docs/manuale/admin.md § "Per gli sviluppatori: rigenerare gli screenshot"):
 *   uv run python manage.py popola_demo --password '<pwd>' --disattiva-rate-limit --ricrea
 *     (--ricrea a ogni giro: il gruppo csq modifica il diario Pantere)
 *   uv run python manage.py runserver            # Django (DEBUG=True: bypass TOTP 000000)
 *   npm run dev                                  # Vite, con PLANCIA_BACKEND se Django non è su :8000
 * Uso:
 *   PLANCIA_DEMO_PASSWORD='<pwd>' npm run manuale:schermate
 *   PLANCIA_MANUALE_URL=http://localhost:5210 PLANCIA_DEMO_PASSWORD=… npm run manuale:schermate -- csq crp
 *
 * Script Node (TypeScript eseguito direttamente da Node ≥ 23, niente tsx): usa la libreria di
 * Playwright, non il test runner, perché è una sequenza di pagine da fotografare e non di test.
 * Gli argomenti (facoltativi) limitano i gruppi: comune, csq, crp, pgv, incaricato, segreteria, admin.
 * I nomi dei file sono stabili: li usano i capitoli in docs/manuale/*.md.
 */
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

import {
  chromium,
  devices,
  type Browser,
  type BrowserContext,
  type Locator,
  type Page,
} from '@playwright/test'

const BASE = process.env.PLANCIA_MANUALE_URL ?? 'http://localhost:5173'
const PASSWORD = process.env.PLANCIA_DEMO_PASSWORD ?? ''
const USCITA = fileURLToPath(new URL('../../docs/manuale/screenshots/', import.meta.url))
const CODICE_MFA = '000000' // MFA_TOTP_INSECURE_BYPASS_CODE di config/settings/dev.py
const TOKEN_INVITO = '5e1f0c2a-7d1b-4c55-9a7e-2b6f3f1d0a01' // popola_demo.TOKEN_INVITO_DEMO

/** Credenziali create da `manage.py popola_demo` (il Capo Squadriglia entra con il codice socio). */
const UTENTI = {
  admin: 'admin@example.org',
  segreteria: 'segreteria@example.org',
  incaricato: 'incaricato@example.org',
  pgv: 'pgv@example.org',
  crp: 'crp@example.org',
  csq: '990101',
} as const
type Ruolo = keyof typeof UTENTI

const DESKTOP = { viewport: { width: 1280, height: 820 }, deviceScaleFactor: 1, locale: 'it-IT' }
const IPHONE = { ...devices['iPhone 15'], deviceScaleFactor: 2, locale: 'it-IT' }

let browser: Browser

async function contesto(mobile = false): Promise<BrowserContext> {
  const ctx = await browser.newContext({ ...(mobile ? IPHONE : DESKTOP), baseURL: BASE })
  // Sidebar sempre espansa negli scatti desktop (preferenza salvata nel browser)
  await ctx.addInitScript(() => localStorage.setItem('plancia:sidebar-compressa', '0'))
  return ctx
}

async function pronta(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle').catch(() => undefined)
  await page
    .locator('.spinner-border')
    .first()
    .waitFor({ state: 'hidden', timeout: 10_000 })
    .catch(() => undefined)
  await page.waitForTimeout(350)
}

async function scatta(
  bersaglio: Page | Locator,
  nome: string,
  opzioni: { pagina?: boolean } = {},
): Promise<void> {
  const percorso = `${USCITA}${nome}.png`
  if ('goto' in bersaglio) {
    await pronta(bersaglio)
    await bersaglio.screenshot({
      path: percorso,
      fullPage: opzioni.pagina ?? false,
      animations: 'disabled',
    })
  } else {
    await bersaglio.scrollIntoViewIfNeeded()
    await bersaglio.page().waitForTimeout(250)
    await bersaglio.screenshot({ path: percorso, animations: 'disabled' })
  }
  console.log(`  ${nome}.png`)
}

/** Pagina a tutta altezza su desktop: lo scroll è dentro `.ag-scroll-area`, si allunga il viewport. */
async function scattaLunga(page: Page, nome: string, altezzaMax = 2000): Promise<void> {
  await pronta(page)
  const altezza = await page.evaluate(() => {
    const area = document.querySelector('.ag-scroll-area')
    const header = document.querySelector('header')
    return (area?.scrollHeight ?? 800) + (header?.getBoundingClientRect().height ?? 0)
  })
  const prima = page.viewportSize()!
  await page.setViewportSize({
    width: prima.width,
    height: Math.min(Math.max(altezza, prima.height), altezzaMax),
  })
  await scatta(page, nome)
  await page.setViewportSize(prima)
}

async function accedi(page: Page, ruolo: Ruolo): Promise<void> {
  await page.goto('/accesso')
  await page.getByLabel('Email o codice socio').fill(UTENTI[ruolo])
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  const mfa = page.getByRole('heading', { name: 'Verifica in due passaggi' })
  const home = page.getByRole('heading', { name: /Benvenuto/ })
  await mfa.or(home).waitFor()
  if (await mfa.isVisible()) {
    await page.getByLabel('Codice').fill(CODICE_MFA)
    await page.getByRole('button', { name: 'Verifica' }).click()
    await home.waitFor()
  }
}

async function sessione(ruolo: Ruolo, mobile = false): Promise<Page> {
  const page = await (await contesto(mobile)).newPage()
  await accedi(page, ruolo)
  return page
}

async function idDiario(page: Page, squadriglia: string): Promise<number> {
  const r = await page.request.get(`/api/v1/diari?q=${encodeURIComponent(squadriglia)}&limit=5`)
  const dati = (await r.json()) as { items: { id: number; squadriglia: string }[] }
  const d = dati.items.find((x) => x.squadriglia === squadriglia)
  if (!d) throw new Error(`Diario ${squadriglia} non trovato: hai eseguito popola_demo?`)
  return d.id
}

async function apriMenuMobile(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Apri menu' }).click()
  await page.waitForTimeout(400)
}

// --- Gruppi di screenshot --------------------------------------------------------------

async function comune(): Promise<void> {
  // Pagina di accesso con il pulsante SSO (in sviluppo i provider non sono configurati: si simula)
  const ctx = await contesto()
  await ctx.route('**/api/v1/sito', async (route) => {
    const r = await route.fetch()
    const dati = await r.json()
    dati.login.provider = [{ id: 'sestante', nome: 'SSO AGESCI Campania' }]
    await route.fulfill({ response: r, json: dati })
  })
  const page = await ctx.newPage()
  await page.goto('/accesso')
  await scatta(page, 'accesso')
  await page.getByLabel('Email o codice socio').fill(UTENTI.incaricato)
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Accedi', exact: true }).click()
  await page.getByRole('heading', { name: 'Verifica in due passaggi' }).waitFor()
  await scatta(page, 'verifica_due_passaggi')
  await ctx.close()

  const mobile = await (await contesto(true)).newPage()
  await mobile.goto('/accesso')
  await scatta(mobile, 'accesso_iphone')
  await mobile.goto(`/invito/${TOKEN_INVITO}`)
  await mobile.getByLabel('Codice socio AGESCI').waitFor()
  await scatta(mobile, 'attivazione_invito_iphone')
  await mobile.context().close()

  // Aggiornamento disponibile: il server dichiara una versione più recente di quella dell'app
  // (la modale compare su ogni pagina, anche su quella di accesso: si entra prima)
  const ctxAgg = await contesto()
  const agg = await ctxAgg.newPage()
  await accedi(agg, 'crp')
  await ctxAgg.route('**/api/v1/sito', async (route) => {
    const r = await route.fetch()
    const dati = await r.json()
    const [maj, min, pat] = String(dati.versione).split('.').map(Number)
    dati.versione = `${maj}.${min}.${(pat ?? 0) + 1}`
    await route.fulfill({ response: r, json: dati })
  })
  await agg.reload()
  const modale = agg.getByRole('dialog', { name: 'Aggiornamento disponibile' })
  await modale.waitFor()
  await scatta(agg, 'aggiornamento_disponibile')
  await agg.getByRole('button', { name: 'Più tardi' }).click()
  await agg.waitForTimeout(400)
  await scatta(agg.locator('footer'), 'footer_versioni')
  await ctxAgg.close()

  // Menu laterale su iPhone e menu utente
  const crp = await sessione('crp', true)
  await apriMenuMobile(crp)
  await scatta(crp, 'menu_iphone')
  await crp.context().close()

  const desk = await sessione('crp')
  // Il pannello utente è in fondo alla sidebar: viewport alto quanto la pagina perché sia visibile
  await desk.goto('/helpdesk')
  await pronta(desk)
  const alta = await desk.evaluate(() => document.documentElement.scrollHeight)
  await desk.setViewportSize({ width: DESKTOP.viewport.width, height: alta })
  await desk.locator('.ag-sidebar__user-toggle').click()
  await desk.waitForTimeout(500)
  await scatta(desk, 'menu_utente')
  await desk.keyboard.press('Escape')
  await desk.setViewportSize(DESKTOP.viewport)
  await desk.goto('/profilo/sicurezza')
  await scattaLunga(desk, 'sicurezza')
  await desk.goto('/profilo')
  await scattaLunga(desk, 'profilo', 1500)
  await desk.context().close()
}

async function csq(): Promise<void> {
  const page = await sessione('csq')
  const id = await idDiario(page, 'Pantere')
  await scatta(page, 'csq_home')
  await page.goto(`/diari/${id}`)
  await scatta(page, 'csq_diario')
  await page.goto(`/diari/${id}/anagrafica`)
  await scatta(page, 'csq_anagrafica')
  await page.goto(`/diari/${id}/presentazione`)
  await page.getByLabel('Cosa sappiamo fare').waitFor()
  await scattaLunga(page, 'csq_presentazione', 1700)
  await page.goto(`/diari/${id}/imprese/1`)
  await page.getByLabel('Perché').waitFor()
  await scatta(page, 'csq_impresa')
  const galleria = page.locator('.galleria-foto').first()
  await scatta(galleria, 'csq_impresa_foto')
  // Salvataggio automatico: modifica in attesa di invio
  await page.getByLabel('Titolo').fill('Un rifugio nel bosco di castagni')
  await scatta(page.locator('.barra-salvataggio'), 'csq_salvataggio_in_corso')
  await page.getByText(/Salvato alle/).waitFor({ timeout: 15_000 })
  await scatta(page.locator('.barra-salvataggio'), 'csq_salvataggio_fatto')
  await page.goto(`/diari/${id}/missione`)
  await page.getByLabel('Descrizione e svolgimento').waitFor()
  await scatta(page, 'csq_missione')
  await page.goto('/helpdesk/nuovo')
  await scatta(page, 'helpdesk_nuovo')
  await page.context().close()

  // Telefono: home, foto, modifica offline in coda
  const tel = await sessione('csq', true)
  await scatta(tel, 'csq_home_iphone')
  await tel.goto(`/diari/${id}/allegati`)
  await scatta(tel, 'csq_foto_iphone')
  await tel.goto(`/diari/${id}/presentazione`)
  const campo = tel.getByLabel('Cosa sappiamo fare')
  await campo.waitFor()
  await tel.context().setOffline(true)
  await tel.evaluate(() => window.dispatchEvent(new Event('offline')))
  await campo.fill(`${await campo.inputValue()} Abbiamo anche imparato a fare i nodi marinari.`)
  await tel.getByRole('button', { name: /da inviare/ }).waitFor({ timeout: 20_000 })
  await tel.evaluate(() => window.scrollTo(0, 0))
  await scatta(tel, 'csq_offline_iphone')
  await tel.context().setOffline(false)
  await tel.evaluate(() => window.dispatchEvent(new Event('online')))
  await tel
    .getByRole('button', { name: /da inviare/ })
    .waitFor({ state: 'hidden', timeout: 20_000 })
  await tel.context().close()
}

async function crp(): Promise<void> {
  const page = await sessione('crp')
  await scatta(page, 'crp_home')
  await page.goto('/diari')
  await scatta(page, 'crp_diari')
  const aquile = await idDiario(page, 'Aquile')
  await page.goto(`/diari/${aquile}`)
  await scatta(page, 'crp_diario')
  await page.goto(`/diari/${aquile}/relazione-finale`)
  await page.getByLabel('Sintesi 1ª impresa').waitFor()
  await scattaLunga(page, 'crp_relazione_finale', 1600)
  const pantere = await idDiario(page, 'Pantere')
  await page.goto(`/diari/${pantere}`)
  await page.getByRole('button', { name: 'Cambia Capo Squadriglia' }).click()
  const dialogo = page.locator('dialog[open]') // su desktop anche la sidebar è un <dialog>
  await dialogo.waitFor()
  await dialogo.getByRole('combobox', { name: 'Nuovo Capo Squadriglia' }).fill('Fe')
  await page.waitForTimeout(900)
  await scatta(page, 'crp_cambia_csq')
  await page.keyboard.press('Escape')
  const volpi = await idDiario(page, 'Volpi')
  await page.goto(`/diari/${volpi}`)
  await scatta(page, 'crp_esito_pubblicato')
  await page.goto(`/diari/${volpi}/pdf`)
  await page.locator('iframe').waitFor()
  await page.waitForTimeout(3000) // il visore PDF del browser disegna dopo il caricamento
  await scatta(page, 'crp_pdf')
  await page.goto('/inviti')
  await scatta(page, 'crp_inviti')
  await page.context().close()
}

async function pgv(): Promise<void> {
  const page = await sessione('pgv')
  await scatta(page, 'pgv_home')
  await page.goto('/diari')
  await scatta(page, 'pgv_diari')
  const falchi = await idDiario(page, 'Falchi')
  await page.goto(`/diari/${falchi}/valutazione`)
  await page.getByRole('heading', { name: 'Proponi valutazione' }).waitFor()
  await scatta(page, 'pgv_valutazione')
  await page.context().close()
}

async function incaricato(): Promise<void> {
  const page = await sessione('incaricato')
  await scattaLunga(page, 'incaricato_home', 1500)
  await page.goto('/diari')
  await scatta(page, 'incaricato_diari')
  const castori = await idDiario(page, 'Castori')
  await page.goto(`/diari/${castori}/valutazione`)
  await page.getByRole('heading', { name: 'Valuta direttamente' }).waitFor()
  await scatta(page, 'incaricato_valuta')
  const lupi = await idDiario(page, 'Lupi')
  await page.goto(`/diari/${lupi}/valutazione`)
  await page.getByRole('heading', { name: /Proposta della Pattuglia GV/ }).waitFor()
  await scatta(page, 'incaricato_revisione')
  const cervi = await idDiario(page, 'Cervi')
  await page.goto(`/diari/${cervi}`)
  await scatta(page, 'incaricato_riapri')
  await page.goto('/edizioni')
  await page.getByRole('link', { name: 'Apri' }).first().click()
  await page.getByRole('button', { name: 'Pubblica esiti' }).click()
  await page.getByRole('dialog', { name: 'Pubblica gli esiti' }).waitFor()
  await scatta(page, 'incaricato_pubblica')
  await page.keyboard.press('Escape')
  await page.goto('/statistiche')
  await scattaLunga(page, 'statistiche', 1700)
  await page.context().close()
}

async function segreteria(): Promise<void> {
  const page = await sessione('segreteria')
  await scatta(page, 'segreteria_home')
  await page.goto('/edizioni')
  await scatta(page, 'edizioni')
  await page.getByRole('link', { name: 'Apri' }).first().click()
  await page.getByRole('heading', { name: /Guidoncini Verdi/ }).waitFor()
  await scatta(page, 'edizione_dettaglio')
  await scatta(
    page.locator('section', { has: page.getByRole('heading', { name: 'Dilazioni' }) }),
    'edizione_dilazioni',
  )
  await scatta(
    page.locator('section', { has: page.getByRole('heading', { name: 'Google Drive' }) }),
    'edizione_drive',
  )
  await page.goto('/utenti')
  await scatta(page, 'utenti')
  await page.goto('/utenti/nuovo')
  await scattaLunga(page, 'utente_nuovo', 1400)
  await page.goto('/utenti')
  await page.getByRole('link', { name: /Dettaglio di De Luca Paolo/ }).click()
  await page.getByRole('heading', { name: 'Assegna ruolo' }).waitFor()
  await scattaLunga(page, 'utente_dettaglio', 1500)
  await page.goto('/gestione/inviti')
  await scattaLunga(page, 'inviti_gestione', 1700)
  await page.goto('/import')
  await scattaLunga(page, 'import', 1700)
  await page
    .getByRole('row', { name: /squadriglie_iscritte_demo/ })
    .getByRole('link', { name: /Dettaglio/ })
    .click()
  await page.getByText('Anomalie da riconciliare').first().waitFor()
  await scattaLunga(page, 'import_dettaglio', 1700)
  // Reparto Orsa Maggiore: ha diari non ancora inviati (Pantere, Aquile, Gabbiani)
  const pantere = await idDiario(page, 'Pantere')
  const r = await page.request.get(`/api/v1/diari/${pantere}`)
  const reparto = ((await r.json()) as { reparto_id: number }).reparto_id
  await page.goto(`/reparti/${reparto}/cambia-capo-reparto`)
  await page.getByText('Diari coinvolti').waitFor()
  await page.getByRole('combobox', { name: 'Nuovo Capo Reparto' }).fill('Gal')
  await page.waitForTimeout(900)
  await scatta(page, 'cambia_crp_reparto')
  await page.goto('/helpdesk')
  await scatta(page, 'helpdesk')
  await page.getByRole('link', { name: /Non riesco a caricare/ }).click()
  await page.getByRole('heading', { name: /Ticket #/ }).waitFor()
  await scatta(page, 'helpdesk_ticket')
  await page.context().close()
}

async function admin(): Promise<void> {
  const page = await sessione('admin')
  await scatta(page, 'admin_home')
  for (const scheda of ['generale', 'email', 'sicurezza', 'sistema', 'template-email', 'pagine']) {
    await page.goto(`/impostazioni/${scheda}`)
    await scattaLunga(page, `impostazioni_${scheda.replace('-', '_')}`, 1800)
  }
  await page.goto('/impostazioni/cache-pdf')
  await scatta(page, 'cache_pdf')
  await page.goto('/impostazioni/log-export')
  await scatta(page, 'log_export')
  await page.goto('/impostazioni/drive')
  await scatta(page, 'impostazioni_drive')
  await page.goto('/impostazioni/aggiornamenti')
  await scattaLunga(page, 'aggiornamenti', 1500)
  await page.context().close()
}

const GRUPPI: Record<string, () => Promise<void>> = {
  comune,
  csq,
  crp,
  pgv,
  incaricato,
  segreteria,
  admin,
}

async function main(): Promise<void> {
  if (!PASSWORD)
    throw new Error('Imposta PLANCIA_DEMO_PASSWORD (la password passata a popola_demo).')
  const scelti = process.argv.slice(2).filter((a) => a !== '--')
  for (const g of scelti) if (!GRUPPI[g]) throw new Error(`Gruppo sconosciuto: ${g}`)
  await mkdir(USCITA, { recursive: true })
  // Chromium completo (headless nuovo): ha il visore PDF, la shell headless no
  browser = await chromium.launch({ channel: 'chromium' })
  try {
    for (const [nome, gruppo] of Object.entries(GRUPPI)) {
      if (scelti.length && !scelti.includes(nome)) continue
      console.log(`[${nome}]`)
      await gruppo()
    }
  } finally {
    await browser.close()
  }
}

await main()
