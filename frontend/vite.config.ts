import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backend = process.env.MONIKRAFT_API ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
      '/residents': backend,
      '/devices': backend,
      '/access-events': backend,
    },
  },
})
