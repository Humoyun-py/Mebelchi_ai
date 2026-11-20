/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8000' } },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: { output: { manualChunks(id: string) { if (id.includes('node_modules/three') || id.includes('@react-three')) return 'three'; if (/node_modules\/(react|react-dom|react-router|react-router-dom|@tanstack|framer-motion|scheduler)\//.test(id)) return 'vendor' } } },
  },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test/setup.ts'], css: false },
})
