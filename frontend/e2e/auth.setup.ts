/**
 * Signs in once and saves the browser's cookies + storage for all other tests
 * (faster, and it respects FALCON's own sign-in rate limit).
 */
import { expect, test as setup } from '@playwright/test'

export const STATE = 'e2e/.auth/analyst.json'

setup('sign in as the demo forensic analyst', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill('a.kumar@falcon.example')
  await page.getByLabel('Password', { exact: true }).fill(process.env.E2E_PASSWORD ?? '')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).not.toHaveURL(/\/login/)
  // Work in the demo case (the app keeps the current case in this browser-storage key).
  await page.evaluate(() => {
    localStorage.setItem(
      'falcon-current-investigation',
      JSON.stringify({ state: { currentInvestigationId: 'CASE-2026-001' }, version: 0 }),
    )
  })
  await page.context().storageState({ path: STATE })
})
