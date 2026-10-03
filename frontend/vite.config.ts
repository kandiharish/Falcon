import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  // Unit tests (Vitest): only src/**/*.test.ts. Browser tests live in e2e/ (Playwright).
  test: {
    include: ['src/**/*.test.ts'],
  },
  server: {
    // FALCON's own port; strictPort fails loudly instead of silently picking another one.
    port: 5190,
    strictPort: true,
    // Forward every /api request to the FastAPI backend. The browser only ever talks to
    // one origin (localhost:5190), so there is no CORS setup and session cookies just work.
    proxy: {
      '/api': 'http://127.0.0.1:8010',
    },
  },
})
