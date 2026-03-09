import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  publicDir: '../public',   // serve project-root /public/ so board-state.json is at /board-state.json
  server: {
    port: 5173,
    open: true,
  },
})
