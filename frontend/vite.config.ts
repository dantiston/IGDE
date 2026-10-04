/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, Vite serves the React app and proxies the JSON API to the
// Django server (python manage.py runserver).  In production Django serves
// the built app from frontend/dist.
const django = process.env.IGDE_DJANGO_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: django, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
