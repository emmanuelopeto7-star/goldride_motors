import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    // Threads, not the default forked processes. Spawning a worker process
    // per test file times out in this checkout - the repo lives under
    // OneDrive, and every process start pays for that.
    pool: 'threads',
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    // Colocated with what they cover, the way the components are.
    include: ['src/**/*.test.{js,jsx}'],
  },
})
