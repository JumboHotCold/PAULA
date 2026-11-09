import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { frontendStamp,buildStampPlugin } from './buildMetadata.mjs'
const stamp=frontendStamp();

export default defineConfig({
  plugins: [
    buildStampPlugin(stamp),
    react(),
    tailwindcss(),
  ],
  define: {__PAULA_FRONTEND_BUILD__:JSON.stringify(stamp)},
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.PAULA_TEST_BACKEND_TARGET || 'http://127.0.0.1:8080',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
