import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,          // bind 0.0.0.0 — reachable on LAN/Tailscale
    port: 5173,
    // Dev proxy: /api -> Kinesis backend (host 8081 -> container 8080), no CORS fuss.
    proxy: {
      '/api': { target: 'http://localhost:8081', changeOrigin: true },
      '/health': { target: 'http://localhost:8081', changeOrigin: true },
    },
  },
})
