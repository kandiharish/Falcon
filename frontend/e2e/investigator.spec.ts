/**
 * The investigator's main journey on the demo case (CASE-2026-001), as a real browser.
 * Needs the demo data: `uv run python -m app.scripts.reset_demo_data --yes` in backend/.
 */
import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const CASE = 'CASE-2026-001'

/** A fresh sign-in (only the sign-out test needs one; the rest reuse auth.setup.ts). */
async function signIn(page: Page, email = 'a.kumar@falcon.example') {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(process.env.E2E_PASSWORD ?? '')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).not.toHaveURL(/\/login/)
}

/** No serious or critical accessibility problems (axe-core, WCAG 2.1 A/AA rules). */
async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  // On failure, name the elements and the measured contrast, so the fix is obvious.
  const report = serious.map((v) => ({
    rule: `${v.id}: ${v.help}`,
    where: v.nodes.slice(0, 8).map((n) => `${n.target.join(' ')} — ${n.failureSummary?.split('\n').slice(1, 2).join(' ').trim()}`),
  }))
  expect(report).toEqual([])
}

test.describe.configure({ mode: 'serial' })

test('signing in shows the command center with real numbers', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Command center' })).toBeVisible()
  const tile = page.getByRole('link', { name: /Evidence items/ })
  await expect(tile).toContainText(/\d+/)
  await expectAccessible(page)
})

test('evidence keeps its fingerprint and shows its integrity', async ({ page }) => {
  await page.goto(`/investigations/${CASE}/evidence/CCTV-001`)
  await expect(page.getByRole('heading', { name: /Rear-door camera/ })).toBeVisible()
  await page.getByRole('tab', { name: 'Integrity' }).click()
  await expect(page.getByText(/[0-9a-f]{64}/).first()).toBeVisible()
  await expectAccessible(page)
})

test('a correlation explains why it exists', async ({ page }) => {
  // Numbers are given strongest first, so COR-001 is the case's strongest relationship:
  // the same van on the rear-door camera and the gate camera.
  await page.goto(`/investigations/${CASE}/correlations/COR-001`)
  await expect(page.getByRole('heading', { name: 'CCTV-001 ⟷ VEH-001' })).toBeVisible()
  await expect(page.getByLabel(/High correlation, score 0\.95/)).toBeVisible()
  await expect(page.getByText('Why this relationship exists')).toBeVisible()
  await expect(page.getByText('potential relationship, not proof')).toBeVisible()
  await expectAccessible(page)
})

test('the relationship graph has an accessible list view', async ({ page }) => {
  await page.goto('/graph')
  await expect(page.getByRole('img', { name: /Relationship graph with \d+ items/ })).toBeVisible()
  await page.getByRole('tab', { name: 'List' }).click()
  await expect(page.getByRole('button', { name: 'Related evidence' }).first()).toBeVisible()
})

test('a report is intact and printable', async ({ page }) => {
  await page.goto('/reports')
  await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible()
  await expect(page.getByText(/Generate a report|RPT-\d{3}/).first()).toBeVisible()
  const first = page.getByRole('link', { name: /^RPT-\d{3}$/ }).first()
  if ((await first.count()) === 0) test.skip(true, 'No report in the demo data yet')
  await first.click()
  await expect(page.getByText('Fingerprint matches: unaltered since generation')).toBeVisible()
  await expect(page.getByText('Part A · Observed evidence')).toBeVisible()
  await expect(page.getByText('Part B · Analytical interpretation')).toBeVisible()
})

test('tasks and global search', async ({ page }) => {
  await page.goto('/tasks')
  await expect(page.getByRole('region', { name: 'In Progress' })).toBeVisible()
  await page.keyboard.press('Control+k')
  await page.getByPlaceholder(/Search IDs/).fill('202 555')
  await expect(page.getByRole('option', { name: /PH001/ })).toBeVisible()
})

const KPHB = 'CASE-2026-005' // the Telangana chain-snatching demo case

test('the case page suggests what to check next', async ({ page }) => {
  await page.goto(`/investigations/${KPHB}`)
  await expect(page.getByText('FALCON suggests')).toBeVisible()
  // The shop camera's clock is 2 minutes fast; FALCON spots it from the ANPR camera.
  await expect(page.getByText("CCTV-001's clock appears to run 1 min 57 s fast (ahead)")).toBeVisible()
  await expect(page.getByRole('link', { name: 'Draft CCTV request' })).toBeVisible()
  await expectAccessible(page)
})

test('a Section 63 certificate is drafted with the evidence hash', async ({ page }) => {
  await page.goto(`/investigations/${KPHB}/evidence/CCTV-001/certificate`)
  await expect(page.getByRole('heading', { name: /SECTION 63\(4\)\(c\) OF THE BHARATIYA SAKSHYA ADHINIYAM/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /HASH value [0-9a-f]{64}/ })).toBeVisible()
  await expectAccessible(page)
})

test('the incident replays on a clock, with the camera clock corrected', async ({ page }) => {
  await page.goto(`/investigations/${KPHB}`) // opening a case makes it the current one
  await expect(page.getByRole('heading', { name: 'KPHB Colony Chain Snatching' })).toBeVisible()
  await page.goto('/timeline?view=replay')
  await expect(page.getByText(/Correct known camera clock errors/)).toBeVisible()
  await page.getByRole('button', { name: '15 min / s' }).click()
  await page.getByRole('button', { name: 'Play' }).click()
  await expect(page.getByText(/^(?!0 )\d+ of \d+ records/)).toBeVisible()
  await expect(page.getByText('clock corrected by 117 s').first()).toBeVisible({ timeout: 15_000 })
})

test.describe('a separate sign-in', () => {
  test.use({ storageState: { cookies: [], origins: [] } }) // not the shared session

  test('signing out locks every page again', async ({ page }) => {
    await signIn(page)
    await page.getByRole('button', { name: /Account menu/ }).click()
    await page.getByRole('menuitem', { name: /Sign out/ }).click()
    await expect(page).toHaveURL(/\/login/)
    await page.goto('/evidence')
    await expect(page).toHaveURL(/\/login/)
    await expectAccessible(page)
  })
})

test.describe('dark theme', () => {
  test.use({ colorScheme: 'dark' }) // FALCON follows the system theme by default

  test('the command center is readable in dark mode too', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Command center' })).toBeVisible()
    await expect(page.locator('html')).toHaveClass(/dark/)
    await expectAccessible(page)
  })
})
