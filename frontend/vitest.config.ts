import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    // jsdom emulates a browser environment for component tests
    environment: 'jsdom',
    // Global imports for describe/it/expect (no need to import in every file)
    globals: true,
    // Exclude E2E tests (Playwright) from Vitest
    exclude: [
      'e2e/**',
      'node_modules/**',
    ],
    // Setup file runs before each test file
    setupFiles: ['./src/test/setup.ts'],
    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.d.ts',
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/main.tsx',
        'src/i18n/**',
      ],
      thresholds: {
        statements: 50,
        branches: 40,
        functions: 50,
        lines: 50,
      },
    },
  },
})
