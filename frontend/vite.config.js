import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3090,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/health': 'http://localhost:8000',
      '/compute-status': 'http://localhost:8000',
      '/memories': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/avatar/action': 'http://localhost:8000',
      '/reload-memory': 'http://localhost:8000',
    },
  },
})
