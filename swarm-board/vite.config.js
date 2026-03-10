import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  publicDir: '../public',   // serve project-root /public/ so board-state.json is at /board-state.json
  server: {
    port: 5173,
    open: true,
    // Proxy all API/gate calls to the Flask backend — eliminates CORS issues
    // regardless of which port Vite starts on.
    proxy: {
      '/api':  { target: 'http://localhost:5003', changeOrigin: true },
      '/gate': { target: 'http://localhost:5003', changeOrigin: true },
    },
  },
})
