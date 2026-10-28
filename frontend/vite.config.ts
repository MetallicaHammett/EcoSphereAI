import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The Django API runs on :8010; proxying keeps the browser on one origin (no CORS setup needed).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8010',
    },
  },
})
