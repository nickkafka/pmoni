import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backend = process.env.PMONI_API ?? 'http://127.0.0.1:8000'

/**
 * Every prefix the backend answers. A prefix missing here does not fail loudly:
 * the dev server answers the application's own HTML instead, so a POST turns into
 * a 404 and a GET into a broken image. Add new backend prefixes here.
 */
const API_PREFIXES = ['auth', 'automation', 'devices', 'residents', 'sigma', 'access-events']

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
      [`^/(${API_PREFIXES.join('|')})(/|$)`]: backend,
    },
  },
})
