import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) return 'vendor'
          if (id.includes('node_modules/leaflet/') || id.includes('node_modules/react-leaflet/')) return 'leaflet'
          if (id.includes('node_modules/zustand/')) return 'zustand'
        }
      }
    }
  },
  server: {
    port: 5173,
    // Proxy API calls to backend during local development
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      }
    }
  }
})
