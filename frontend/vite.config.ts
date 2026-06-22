import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
    },
  },
  build: {
    // Enable CSS code splitting so styles are loaded per-page, not all upfront.
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        // Manual chunk splitting: group vendor libraries into separate chunks
        // for better caching. When app code changes, users still have cached
        // vendor chunks, reducing re-download size on updates.
        manualChunks: {
          // React core + router
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // TanStack Query for data fetching
          'vendor-query': ['@tanstack/react-query'],
          // Lucide icons (relatively large, rarely changes)
          'vendor-icons': ['lucide-react'],
          // i18n (custom implementation, no external deps needed)
        },
      },
    },
    // Use esbuild for minification (built into Vite, no extra dep needed)
    minify: 'esbuild',
    esbuild: {
      drop: ['console', 'debugger'],
    },
  },
})
