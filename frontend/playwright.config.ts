/**
 * End-to-end tests: a real browser clicks through the real app (backend + database + demo data).
 *
 *   npm run e2e            (the dev servers must be running and the demo data seeded)
 *
 * Locally the tests drive Microsoft Edge (already on every Windows PC, nothing to download);
 * in CI on Linux, Playwright's own Chromium. The demo password comes from E2E_PASSWORD or the
 * repository's .env file (DEMO_PASSWORD) and is never printed.
 */
import { readFileSync } from 'node:fs'
import { defineConfig } from '@playwright/test'

function demoPassword(): string {
  if (process.env.E2E_PASSWORD) return process.env.E2E_PASSWORD
  try {
    const line = readFileSync(new URL('../.env', import.meta.url), 'utf8')
      .split(/\r?\n/)
      .find((l) => l.startsWith('DEMO_PASSWORD='))
    return line ? line.slice('DEMO_PASSWORD='.length).replace(/^["']|["']$/g, '') : ''
  } catch {
    return ''
  }
}
process.env.E2E_PASSWORD = demoPassword()

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false, // one shared demo database: keep tests in order
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5190',
    channel: process.env.CI ? undefined : 'msedge',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'investigator',
      testMatch: /.*\.spec\.ts/,
      dependencies: ['setup'],
      use: { storageState: 'e2e/.auth/analyst.json' },
    },
  ],
})
