import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
